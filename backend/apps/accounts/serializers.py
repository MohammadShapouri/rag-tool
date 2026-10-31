from rest_framework import serializers
from .models import User, GlobalConfig

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'credit', 'is_superuser', 'date_joined')
        read_only_fields = ('id', 'credit', 'is_superuser', 'date_joined')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password')

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class GlobalConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalConfig
        fields = ('default_user_credit', 'updated_at')


class StaffUserBriefSerializer(serializers.ModelSerializer):
    """Brief serialized user for department staff assignment rosters."""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'credit')
        read_only_fields = ('id', 'username', 'email', 'first_name', 'last_name', 'credit')


class AdminUserSerializer(serializers.ModelSerializer):
    """Full user serializer for Superuser administration."""
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'credit', 'is_superuser', 'password', 'date_joined'
        )
        read_only_fields = ('id', 'date_joined')

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        return User.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
