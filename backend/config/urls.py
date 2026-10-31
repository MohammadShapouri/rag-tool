"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from apps.apikeys.views import OrganizationAPIKeyViewSet
from apps.apikeys.external_views import ExternalSupportRAGView

def health_check(request):
    """Liveness probe for Docker / Kubernetes health checks."""
    return JsonResponse({"status": "healthy", "service": "enterprise-rag-backend"})

urlpatterns = [
    # Built-in Django Admin (Superusers only)
    path('admin/', admin.site.urls),

    # System Health Check
    path('api/health/', health_check, name='health_check'),

    # 1. Accounts & Authentication (Register, JWT, Profile, Superuser Global Config)
    path('api/auth/', include('apps.accounts.urls')),

    # 2. Organizations & Departments (CRUD, Staff Assignment, Manager AI Endpoint Settings)
    path('api/organizations/', include('apps.organizations.urls')),

    # 3. Documents & Ingestion (Upload, List, Delete, Background Celery Vectorization)
    path('api/documents/', include('apps.documents.urls')),

    # 4. Chat & Internal RAG (Multi-Department Retrieval, History, Streaming)
    path('api/chat/', include('apps.chat.urls')),

    # 5. Billing & Credit Ledger (Rates, Transaction History, Superuser Top-ups)
    path('api/credits/', include('apps.credits.urls')),

    # 6. External Support Widget & Public API (Scoped API Keys, Website Integration)
    path('api/external/', include('apps.apikeys.urls')),

    # 7. Audit Logs & VectorDB Diagnostics (Superuser telemetry & Manager logs)
    path('api/audit-logs/', include('apps.logs.urls')),
    path('api/logs/', include('apps.logs.urls')),

    # Frontend Route Aliases for Organization API Keys & Public Chat
    path('api/v1/public/chat/', ExternalSupportRAGView.as_view(), name='public_chat_v1'),
    path('api/organizations/<int:organization_id>/api-keys/', OrganizationAPIKeyViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='org_api_keys_nested_list'),
    path('api/organizations/<int:organization_id>/api-keys/<str:pk>/', OrganizationAPIKeyViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='org_api_keys_nested_detail'),
]

# Serve user uploaded files (logos, documents) and static assets during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
