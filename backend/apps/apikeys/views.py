from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db.models import Q
from .models import OrganizationAPIKey
from .serializers import OrganizationAPIKeySerializer
from apps.organizations.permissions import IsOrgManager

class OrganizationAPIKeyViewSet(viewsets.ModelViewSet):
    """
    CRUD view for managers to create and revoke external API keys.
    """
    serializer_class = OrganizationAPIKeySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = OrganizationAPIKey.objects.all()
        org_id = self.kwargs.get('organization_id') or self.request.query_params.get('organization') or self.request.query_params.get('organization_id')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        if user.is_superuser:
            return qs
        return qs.filter(organization__manager=user)

    def perform_destroy(self, instance):
        # Soft-revoke
        instance.is_active = False
        instance.save(update_fields=['is_active'])
