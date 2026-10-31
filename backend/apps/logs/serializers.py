from rest_framework import serializers
from .models import AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(source='organization.id', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True, allow_null=True)
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = (
            'id', 'timestamp', 'organization_id', 'organization_name',
            'department_ids', 'department_names', 'source',
            'api_key_name', 'api_key_preview', 'user_id', 'username',
            'query', 'response', 'latency_ms', 'tokens_used',
            'status', 'error_message', 'vectordb_details', 'database_details'
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        # Strips deep VectorDB telemetry for non-superusers (e.g. Org Managers)
        if not (request and request.user and request.user.is_superuser):
            data.pop('vectordb_details', None)
            data.pop('database_details', None)
        return data