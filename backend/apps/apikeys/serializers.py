from rest_framework import serializers
from .models import OrganizationAPIKey
from apps.organizations.models import Department

class OrganizationAPIKeySerializer(serializers.ModelSerializer):
    organization_id = serializers.IntegerField(write_only=True, required=False)
    scope_type = serializers.ChoiceField(choices=['all', 'specific'], required=False, default='all')
    department_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list
    )
    scoped_departments = serializers.SerializerMethodField(read_only=True)
    raw_api_key = serializers.CharField(read_only=True)
    key = serializers.CharField(read_only=True)

    class Meta:
        model = OrganizationAPIKey
        fields = (
            'id', 'organization', 'organization_id', 'name', 'key', 'prefix',
            'all_departments', 'scope_type', 'department_ids', 'scoped_departments',
            'is_active', 'request_count', 'created_at', 'last_used_at', 'raw_api_key'
        )
        read_only_fields = ('id', 'prefix', 'created_at', 'last_used_at', 'request_count', 'key', 'raw_api_key')
        extra_kwargs = {
            'organization': {'required': False}
        }

    def get_scoped_departments(self, obj):
        if obj.all_departments:
            return "ALL"
        return list(obj.departments.values('id', 'name'))

    def validate(self, attrs):
        org = attrs.get('organization')
        all_depts = attrs.get('all_departments', False)
        dept_ids = self.initial_data.get('department_ids', [])

        user = self.context['request'].user
        if not (user.is_superuser or org.manager == user):
            raise serializers.ValidationError("Only organization managers can create API keys.")

        if not all_depts and not dept_ids:
            raise serializers.ValidationError("You must select at least one department or enable all_departments.")

        if not all_depts and dept_ids:
            valid_ids = set(org.departments.values_list('id', flat=True))
            if not set(dept_ids).issubset(valid_ids):
                raise serializers.ValidationError("One or more selected department IDs do not belong to this organization.")

        return attrs

    def create(self, validated_data):
        dept_ids = validated_data.pop('department_ids', [])
        user = self.context['request'].user
        
        instance, raw_key = OrganizationAPIKey.generate_key(
            organization=validated_data['organization'],
            created_by=user,
            name=validated_data['name'],
            all_departments=validated_data.get('all_departments', False),
            department_ids=dept_ids
        )
        instance.raw_api_key = raw_key
        return instance
