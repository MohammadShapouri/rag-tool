# config/throttling.py
import os
import re
import time
import yaml
import hashlib
import logging
from pathlib import Path
from django.conf import settings
from rest_framework.throttling import BaseThrottle
import redis

logger = logging.getLogger(__name__)

# Connect to Redis using Celery's broker URL or default Redis port
try:
    redis_client = redis.Redis.from_url(
        getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        socket_connect_timeout=2,
        socket_timeout=2
    )
except Exception as e:
    logger.error(f"Failed to initialize Redis connection for rate limiter: {e}")
    redis_client = None


def parse_duration_to_seconds(duration_str: str) -> int:
    """
    Converts human-readable duration strings into integer seconds.
    Supports:
      '10s' -> 10 seconds
      '1m'  -> 60 seconds
      '1h'  -> 3600 seconds
      '1d'  -> 86400 seconds
    """
    match = re.match(r"^(\d+)([smhd])$", str(duration_str).strip().lower())
    if not match:
        raise ValueError(f"Invalid duration format: '{duration_str}'. Use s, m, h, or d (e.g., '1m', '2h').")
    
    count, unit = int(match.group(1)), match.group(2)
    multipliers = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
    return count * multipliers[unit]


class YamlRateLimiter:
    """
    Parses and caches the rate limit definitions from config/rate_limits.yml.
    Hot-reloads automatically when the file's modification time changes.
    """
    _rules = None
    _last_loaded = 0

    @classmethod
    def load_rules(cls):
        config_path = getattr(
            settings,
            'RATE_LIMIT_CONFIG_PATH',
            Path(settings.BASE_DIR) / 'config' / 'rate_limits.yml'
        )

        if not os.path.exists(config_path):
            return {'defaults': [], 'endpoints': []}

        try:
            mtime = os.path.getmtime(config_path)
            if cls._rules is None or mtime > cls._last_loaded:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}

                parsed_endpoints = []
                for ep in data.get('endpoints', []):
                    compiled_pattern = re.compile(ep['path']) if ep.get('is_regex') else None
                    parsed_limits = [
                        {
                            'requests': int(lim['requests']),
                            'window_seconds': parse_duration_to_seconds(lim['window']),
                            'window_raw': str(lim['window'])
                        }
                        for lim in ep.get('limits', [])
                    ]
                    parsed_endpoints.append({
                        'path': ep['path'],
                        'pattern': compiled_pattern,
                        'limits': parsed_limits
                    })

                parsed_defaults = [
                    {
                        'requests': int(lim['requests']),
                        'window_seconds': parse_duration_to_seconds(lim['window']),
                        'window_raw': str(lim['window'])
                    }
                    for lim in data.get('defaults', [])
                ]

                cls._rules = {'defaults': parsed_defaults, 'endpoints': parsed_endpoints}
                cls._last_loaded = mtime

            return cls._rules
        except Exception as err:
            logger.error(f"Error parsing rate_limits.yml: {err}")
            return cls._rules or {'defaults': [], 'endpoints': []}

    @classmethod
    def get_limits_for_path(cls, request_path: str):
        rules = cls.load_rules()
        for ep in rules.get('endpoints', []):
            if ep['pattern'] and ep['pattern'].match(request_path):
                return ep['limits']
            elif ep['path'] == request_path:
                return ep['limits']
        return rules.get('defaults', [])


# Atomic Lua script executed directly inside Redis memory space.
# Completely eliminates Time-Of-Check to Time-Of-Use (TOCTOU) race conditions.
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local clear_before = now - window

-- 1. Evict hits that fall outside the active sliding window
redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)

-- 2. Count current hits within the window
local current_requests = redis.call('ZCARD', key)

-- 3. If within threshold, record timestamp atomically and update TTL
if current_requests < limit then
    redis.call('ZADD', key, now, now)
    redis.call('EXPIRE', key, window + 10)
    return {1, limit - current_requests - 1, 0}
else
    -- Over limit: calculate required wait time based on oldest recorded timestamp
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = window
    if #oldest > 0 then
        retry_after = math.ceil(window - (now - tonumber(oldest[2])))
    end
    if retry_after <= 0 then
        retry_after = 1
    end
    return {0, 0, retry_after}
end
"""

# Register Lua script if Redis is reachable
rate_limit_script = None
if redis_client:
    try:
        rate_limit_script = redis_client.register_script(SLIDING_WINDOW_LUA)
    except Exception as e:
        logger.error(f"Failed to register Redis rate limiter script: {e}")


class YamlConfiguredThrottle(BaseThrottle):
    """
    Enterprise-grade sliding-window rate limiter backed by Redis.
    Reads duration windows dynamically from config/rate_limits.yml.
    """
    def get_ident(self, request):
        """
        Determines the unique client identifier:
        1. API Key ID (if authenticated via X-API-Key)
        2. User ID (if authenticated via JWT / Session)
        3. Client IP (if unauthenticated / anonymous)
        """
        if hasattr(request, 'api_key_obj') and request.api_key_obj:
            return f"apikey:{request.api_key_obj.id}"
        
        if request.user and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Resolve real client IP behind reverse proxies (Nginx / Cloudflare / Docker)
        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            client_ip = xff.split(',')[0].strip()
        else:
            client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        return f"ip:{client_ip}"

    def allow_request(self, request, view):
        if not redis_client or not rate_limit_script:
            # Fail-open: don't block traffic if Redis is unreachable
            return True

        limits = YamlRateLimiter.get_limits_for_path(request.path)
        if not limits:
            return True

        ident = self.get_ident(request)
        
        # Deterministic MD5 hash of path to ensure consistent keys across all worker processes
        path_hash = hashlib.md5(request.path.encode('utf-8')).hexdigest()[:12]
        now = time.time()
        max_retry_after = 0

        try:
            # Atomically evaluate each configured window rule (e.g. 1m, 1h, 1d)
            for rule in limits:
                window = rule['window_seconds']
                max_requests = rule['requests']
                key = f"rl:{ident}:{path_hash}:{window}"

                # Execute Lua script inside Redis
                allowed, remaining, retry_after = rate_limit_script(
                    keys=[key],
                    args=[now, window, max_requests]
                )

                if allowed == 0:
                    self.retry_after = max(max_retry_after, retry_after)
                    return False

            return True

        except redis.RedisError as redis_err:
            # Log Redis failure and fail-open to preserve API availability
            logger.warning(f"Rate limiter Redis error: {redis_err}. Allowing request as fail-open.")
            return True

    def wait(self):
        """Returns the number of seconds the client must wait before retrying."""
        return getattr(self, 'retry_after', 60)