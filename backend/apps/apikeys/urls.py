from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import OrganizationAPIKeyViewSet
from .external_views import ExternalSupportRAGView

router = DefaultRouter()
router.register(r'keys', OrganizationAPIKeyViewSet, basename='organization-api-keys')

urlpatterns = [
    # External Widget Query Endpoints
    path('v1/query/', ExternalSupportRAGView.as_view(), name='external_support_query'),
    path('v1/public/chat/', ExternalSupportRAGView.as_view(), name='public_chat_query'),
] + router.urls