from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'organization', 'source', 'status', 'latency_ms', 'tokens_used')
    list_filter = ('source', 'status', 'organization')
    search_fields = ('query', 'response', 'api_key_name', 'user__username')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False