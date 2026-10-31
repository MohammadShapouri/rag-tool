from django.contrib import admin
from .models import CreditRateConfig, CreditTransaction

@admin.register(CreditRateConfig)
class CreditRateConfigAdmin(admin.ModelAdmin):
    list_display = ('base_query_fee', 'cost_per_chunk_retrieved', 'cost_per_1k_prompt_tokens', 'cost_per_1k_completion_tokens', 'cost_per_document_page', 'min_query_balance')

@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'payer', 'actor', 'organization', 'transaction_type', 'amount', 'balance_after')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('payer__email', 'actor__username', 'description')
    readonly_fields = ('payer', 'actor', 'organization', 'transaction_type', 'amount', 'balance_after', 'description', 'metadata', 'created_at')

    def has_add_permission(self, request):
        return False  # Prevent manual modifications outside the service

    def has_delete_permission(self, request, obj=None):
        return False  # Audit logs must be immutable
