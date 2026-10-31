import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import OrganizationAPIKey

class APIKeyAuthentication(BaseAuthentication):
    """
    Authenticates requests via:
      Header: X-API-Key: rag_live_...
      or
      Header: Authorization: Bearer rag_live_...
    """
    def authenticate(self, request):
        raw_key = request.headers.get('X-API-Key')
        if not raw_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer rag_live_'):
                raw_key = auth_header.split(' ')[1]

        if not raw_key:
            return None

        if not raw_key.startswith('rag_live_') or len(raw_key) < 20:
            raise AuthenticationFailed("Invalid API key format.")

        prefix = raw_key[:12]
        candidate_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        try:
            api_key = OrganizationAPIKey.objects.select_related('organization__manager').get(
                prefix=prefix,
                hashed_key=candidate_hash,
                is_active=True
            )
        except OrganizationAPIKey.DoesNotExist:
            raise AuthenticationFailed("Invalid or revoked API key.")

        # Update last used timestamp
        OrganizationAPIKey.objects.filter(id=api_key.id).update(last_used_at=timezone.now())

        # Attach custom metadata to the request
        request.api_key_obj = api_key
        request.organization = api_key.organization

        # Assign user as the Organization Manager so all credit deductions bill the owner
        return (api_key.organization.manager, api_key)
