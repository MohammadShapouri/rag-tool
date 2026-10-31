from django.contrib import admin
from .models import OrganizationAPIKey

@admin.register(OrganizationAPIKey)
class OrganizationAPIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'prefix', 'all_departments', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('is_active', 'all_departments', 'organization')
    search_fields = ('name', 'prefix', 'organization__name')
    readonly_fields = ('prefix', 'hashed_key', 'created_at', 'last_used_at')