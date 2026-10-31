from rest_framework import serializers
from .models import ChatSession, ChatMessage
from apps.organizations.models import Department

class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ('id', 'role', 'content', 'sources', 'created_at')

class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    department_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=True
    )

    class Meta:
        model = ChatSession
        fields = ('id', 'organization', 'title', 'selected_departments', 'department_ids', 'messages', 'created_at')
        read_only_fields = ('id', 'selected_departments', 'created_at')

    def create(self, validated_data):
        dept_ids = validated_data.pop('department_ids', [])
        user = self.context['request'].user
        org = validated_data['organization']

        # Validate access to departments
        for d_id in dept_ids:
            dept = Department.objects.get(id=d_id, organization=org)
            if not (user.is_superuser or org.manager == user or user in dept.staffs.all()):
                raise serializers.ValidationError(f"Unauthorized department selection: ID {d_id}")

        session = ChatSession.objects.create(user=user, **validated_data)
        session.selected_departments.set(dept_ids)
        return session
