from rest_framework import serializers
from .models import Organization, Department
from apps.accounts.serializers import UserSerializer

class DepartmentSerializer(serializers.ModelSerializer):
    staff_count = serializers.IntegerField(source='staffs.count', read_only=True)
    staffs = UserSerializer(many=True, read_only=True)
    staff_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Department
        fields = (
            'id', 'organization', 'name', 'description', 
            'department_manager', 'is_default', 'staff_count', 'staffs', 'staff_ids'
        )
        read_only_fields = ('id', 'is_default')

    def create(self, validated_data):
        staff_ids = validated_data.pop('staff_ids', [])
        dept = Department.objects.create(**validated_data)
        if staff_ids:
            dept.staffs.set(staff_ids)
        return dept

    def update(self, instance, validated_data):
        staff_ids = validated_data.pop('staff_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if staff_ids is not None:
            instance.staffs.set(staff_ids)
        return instance

class OrganizationSerializer(serializers.ModelSerializer):
    departments = DepartmentSerializer(many=True, read_only=True)
    staffs = UserSerializer(many=True, read_only=True)
    staff_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    class Meta:
        model = Organization
        fields = (
            'id', 'name', 'description', 'logo', 'manager', 
            'ai_endpoint', 'ai_port', 'ai_api_key', 'ai_model',
            'departments', 'staffs', 'staff_ids'
        )
        read_only_fields = ('id', 'manager')

    def create(self, validated_data):
        staff_ids = validated_data.pop('staff_ids', [])
        user = self.context['request'].user
        org = Organization.objects.create(manager=user, **validated_data)
        if staff_ids:
            org.staffs.set(staff_ids)
            # Auto-assign added staffs to Default Department
            default_dept = org.departments.filter(is_default=True).first()
            if default_dept:
                default_dept.staffs.add(*staff_ids)
        return org

    def update(self, instance, validated_data):
        staff_ids = validated_data.pop('staff_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if staff_ids is not None:
            instance.staffs.set(staff_ids)
        return instance
