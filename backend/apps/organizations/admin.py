from django.contrib import admin
from .models import Organization, Department

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'manager', 'ai_endpoint', 'ai_port', 'created_at')
    search_fields = ('name', 'manager__email')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'department_manager', 'is_default')
    list_filter = ('organization', 'is_default')
