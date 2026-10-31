# RAG-Tool (Backend)

An enterprise-grade, self-hosted Retrieval-Augmented Generation (RAG) backend built with **Django REST Framework**, **Celery**, and **Qdrant**.

Designed for privacy-first, on-premises execution with zero cloud lock-in. Features strict multi-tenant organization hierarchies, department-level data isolation, an atomic two-phase credit metering engine, Redis sliding-window rate limiting, and scoped public API key integration for customer support widgets.

---

## Key Capabilities

* **Multi-Tenancy & Department Isolation (RBAC):**
  * **Superuser:** Complete platform governance, system telemetry, and rate/credit configuration.
  * **Organization Manager:** Owns organization settings, custom LLM endpoints (Ollama/vLLM), departments, and scoped API keys.
  * **Department Manager & Staff:** Scoped document access; personnel can only retrieve knowledge from explicitly assigned departments.
  * *No `is_staff` database column:* Administrative permissions are determined strictly via `is_superuser` and role relations.

* **Two-Phase Atomic Credit Engine (Hold & Settle):**
  * Solves Time-of-Check to Time-of-Use (TOCTOU) race conditions during parallel requests using `select_for_update()`.
  * Places a pre-authorization hold on the Organization Manager's balance before calling vector search or inference.
  * Settles exact compute costs post-generation (prompt tokens, completion tokens, retrieved chunks, and ingestion page counts) and reconciles the hold.
  * Automatic refund rollback if the inference engine or vector database fails.

* **Document Ingestion & Parsing Pipeline:**
  * Asynchronous document processing via Celery task workers.
  * Dynamic database row-locking (`select_for_update(nowait=True)` on Postgres with safe fallback on SQLite) prevents double-billing and duplicate task execution.
  * PDF and text extraction with sliding-window chunking (500 words with 50-word overlap).
  * Chunks indexed into Qdrant with payload metadata filters (`organization_id`, `department_id`, `document_id`).

* **Single-Instance AI Clients & Unified RAG Service:**
  * Lazy process-wide singletons for `SentenceTransformer` and `QdrantClient` (`config/ai_clients.py`) eliminate redundant model reloads and prevent RAM exhaustion.
  * Dynamic prompt builder injects organization-level custom directives and personas into retrieval context.

* **Redis Sliding-Window Rate Limiter:**
  * Multi-window rate limiting defined declaratively via `config/rate_limits.yml`.
  * Atomic Redis Lua script prevents burst-race conditions across multiple WSGI/ASGI worker processes.
  * Dynamic hot-reloading detects on-disk configuration changes without restarting the server.

* **External Support Widget & API Key Subsystem:**
  * Organization Managers can provision secure API keys (`rag_live_...`) scoped to specific public departments.
  * Public integration endpoint (`/api/v1/public/chat/`) allows external customer websites to query support knowledge without requiring user account credentials.
  * Automatically tracks cumulative API key request counts via atomic database increments.

* **Audit Logging & VectorDB Telemetry:**
  * Comprehensive logging of user queries, synthesized outputs, token counts, and end-to-end latencies.
  * Deep diagnostics (vector collection names, cosine similarity scores, dense dimensions, and Qdrant cluster host details).
  * Role-based serialization: superusers receive full telemetry; managers receive a sanitized view with internal infrastructure details stripped.

* **Flexible Database Engine:**
  * Runs on **SQLite** out of the box in development (`DEBUG=True`).
  * Runs on **PostgreSQL** in production (`DEBUG=False`), automatically adjusting lock mechanics.

---

## Project Structure

```text
rag-tool/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── __init__.py          # Celery app export
│   ├── ai_clients.py        # Process-wide SentenceTransformer & Qdrant singletons
│   ├── asgi.py              # ASGI entry point
│   ├── celery.py            # Celery configuration
│   ├── rate_limits.yml      # YAML rate limit rules
│   ├── settings.py          # Unified settings (SQLite/Postgres toggle)
│   ├── throttling.py        # Redis Lua sliding-window rate limiter
│   ├── urls.py              # Root routing table & public aliases
│   └── wsgi.py              # WSGI entry point
└── apps/
    ├── accounts/            # Custom User (no is_staff), Auth & Global Config
    ├── organizations/       # Organizations, Departments & Staff Assignments
    ├── documents/           # Uploads & Celery background ingestion pipeline
    ├── chat/                # Sessions, Messages & Unified RAG Engine
    ├── credits/             # Credit pricing rates & immutable transaction ledger
    ├── apikeys/             # Scoped API keys & external website chat endpoints
    └── logs/                # Audit logging & VectorDB diagnostic telemetry
```

---

## Prerequisites

Before running the application locally, ensure you have the following installed:

1. **Python 3.11+**
2. **Redis Server** (required for Celery broker and the rate limiter):
   ```bash
   # Ubuntu / Debian
   sudo apt install redis-server && sudo systemctl start redis
   
   # macOS (Homebrew)
   brew install redis && brew services start redis
   ```
3. **Qdrant Vector Database**:
   Download and run the standalone binary:
   ```bash
   # Download binary for Linux/macOS
   curl -s https://raw.githubusercontent.com/qdrant/qdrant/master/PACKAGING/gh-actions/get-qdrant.sh | bash
   ./qdrant
   ```
   *Qdrant will listen on `http://localhost:6333` by default.*
4. **Ollama** (Local LLM host):
   Install from [ollama.com](https://ollama.com) and pull your preferred model:
   ```bash
   ollama pull llama3
   ollama serve
   ```

---

## Installation & Local Setup

### 1. Clone Repository & Setup Virtual Environment

```bash
git clone https://github.com/your-username/rag-tool.git
cd rag-tool
```

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

For CPU-only environments, install PyTorch with the CPU index first to minimize download size:

```bash
pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

### 3. Environment Configuration

Copy the sample environment file:

```bash
cp .env.example .env
```

Ensure `.env` contains your local settings:

```ini
SECRET_KEY=your-secure-django-secret-key
DEBUG=True
ALLOWED_HOSTS=*

# SQLite mode active when DEBUG=True
USE_SQLITE=True

# Celery & Rate Limiter Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Qdrant Vector Database
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=enterprise_knowledge

# Embedding Model
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
```

### 4. Database Migrations & Initial Superuser

```bash
# Apply migrations across all apps
python manage.py makemigrations accounts organizations documents chat credits apikeys logs
python manage.py migrate

# Create the initial Superuser account
python manage.py createsuperuser
```

---

## Running the Application

### Terminal 1: Celery Ingestion Worker
Start the background worker to handle document text extraction, chunking, and Qdrant indexing:

```bash
source venv/bin/activate
celery -A config worker -l info
```
*(On Windows environments, append `--pool=solo` to the command).*

### Terminal 2: Django ASGI Server
Run the local development server:

```bash
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```
Or with Uvicorn:
```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints Reference

All endpoints are prefixed with `/api/`.

### 1. Authentication & Users (`apps/accounts`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/register/` | Public | Register new user account. |
| `POST` | `/api/auth/token/` | Public | Obtain JWT access and refresh tokens. |
| `POST` | `/api/auth/token/refresh/` | Public | Refresh expired access token. |
| `GET` | `/api/auth/me/` | Authenticated | Retrieve current user profile and credit balance. |
| `GET` | `/api/auth/users/` | Authenticated | List brief user roster for staff assignments. |
| `PUT/DEL`| `/api/auth/users/<id>/` | Superuser | Modify profiles, adjust balances, or delete users. |
| `GET/PUT`| `/api/auth/admin/global-config/`| Superuser | Configure default signup credits. |

### 2. Organizations & Departments (`apps/organizations`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/organizations/` | Authenticated | List organizations where user is manager or staff. |
| `POST` | `/api/organizations/` | Authenticated | Create a new organization (user becomes Manager). |
| `PUT/DEL`| `/api/organizations/<id>/` | Manager / Superuser | Update AI inference gateway settings or delete org. |
| `POST` | `/api/organizations/<id>/assign-staff/` | Manager / Superuser | Assign staff members to org/departments. |
| `GET` | `/api/organizations/departments/?organization=<id>` | Scoped | List accessible departments. |
| `POST` | `/api/organizations/departments/` | Manager / Superuser | Create an isolated department. |
| `PUT/DEL`| `/api/organizations/departments/<id>/` | Dept Manager / Org Mgr | Manage or delete a department. |

### 3. Document Ingestion (`apps/documents`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/documents/?department=<id>` | Scoped | List documents and chunk/vector metrics. |
| `POST` | `/api/documents/` | Dept Staff / Mgr | Upload PDF/TXT; enqueues Celery indexing. |
| `DELETE` | `/api/documents/<id>/` | Dept Mgr / Org Mgr | Purge physical file, record, and Qdrant points. |

### 4. Chat & Internal RAG (`apps/chat`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET/POST`| `/api/chat/sessions/` | Authenticated | List or create multi-department chat sessions. |
| `GET` | `/api/chat/sessions/<id>/messages/` | Session Owner / Superuser | Retrieve chronological conversation turns. |
| `POST` | `/api/chat/sessions/<id>/query/` | Session Owner | Execute credit-metered RAG query against scoped departments. |

### 5. Credits & Audit Ledger (`apps/credits`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/credits/history/` | Manager / Superuser | View immutable credit deduction history. |
| `GET/PUT`| `/api/credits/rates/` | Superuser | Inspect or adjust pricing table. |
| `POST` | `/api/credits/admin/topup/` | Superuser | Manually grant credits to any user. |

### 6. API Keys & External Chat Integration (`apps/apikeys`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET/POST`| `/api/organizations/<org_id>/api-keys/` | Org Manager | Provision scoped API keys (`rag_live_...`). |
| `DEL` | `/api/organizations/<org_id>/api-keys/<id>/` | Org Manager | Revoke an API key. |
| `POST` | `/api/v1/public/chat/` | Header: `X-API-Key` | Public support query endpoint for external webchat. |

### 7. Audit Logs & Diagnostics (`apps/logs`)
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/audit-logs/?organization=<id>` | Manager / Superuser | Inspect query logs, latencies, tokens, and VectorDB telemetry. |

---

## Testing External Public Chat (cURL Example)

Managers can embed their API key directly into website chat widgets. External requests do not require session cookies or user login:

```bash
curl -X POST http://localhost:8000/api/v1/public/chat/ \
  -H "Content-Type: application/json" \
  -H "X-API-Key: rag_live_your_generated_api_key" \
  -d '{
    "query": "What is the return policy?",
    "session_id": "customer_session_102"
  }'
```

---

## Running Verification Suite

A verification script is included to confirm that all services, database tables, and routes are functional:

```bash
python manage.py shell -c "
from rest_framework.test import APIClient
client = APIClient()
res = client.get('/api/health/')
assert res.status_code == 200
print('System status:', res.json())
"
```