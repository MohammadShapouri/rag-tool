from rest_framework import viewsets, permissions
from .models import AuditLog
from .serializers import AuditLogSerializer

class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/audit-logs/?organization=<orgId>
    - Superusers: Full query logs including vector collection names, cosine scores, and host telemetry.
    - Organization Managers: Scoped to their managed organizations; internal telemetry is stripped.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AuditLog.objects.select_related('organization', 'user').all()

        org_filter = self.request.query_params.get('organization')
        if org_filter:
            qs = qs.filter(organization_id=org_filter)

        if user.is_superuser:
            return qs

        # Org managers can only view logs from organizations they own
        return qs.filter(organization__manager=user)