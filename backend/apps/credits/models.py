from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.organizations.models import Organization

class CreditRateConfig(models.Model):
    """
    Configurable pricing table managed by Superusers.
    Singleton pattern.
    """
    base_query_fee = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.5000'))
    cost_per_chunk_retrieved = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.1000'))
    cost_per_1k_prompt_tokens = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.5000'))
    cost_per_1k_completion_tokens = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('1.5000'))
    cost_per_document_page = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('0.2500'))
    min_query_balance = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal('1.0000'))
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_rates(cls):
        rates, _ = cls.objects.get_or_create(pk=1)
        return rates

    def __str__(self):
        return f"Pricing Rates (Base: {self.base_query_fee}, Prompt/1k: {self.cost_per_1k_prompt_tokens})"


class CreditTransaction(models.Model):
    """
    Immutable audit ledger for every single credit movement.
    """
    TRANSACTION_TYPES = (
        ('RAG_QUERY', 'RAG Retrieval & Generation'),
        ('DOCUMENT_INGESTION', 'Document Embedding & Ingestion'),
        ('INITIAL_SIGNUP', 'New User Bonus'),
        ('ADMIN_TOPUP', 'Superuser Manual Adjustment'),
        ('PURCHASE', 'Credit Purchase'),
    )

    # The payer (Always the Organization Manager for org-level actions)
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_transactions'
    )
    # The actor who executed the action (e.g., a Staff querying documents)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_transactions'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='credit_transactions'
    )
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Negative for deductions, positive for top-ups"
    )
    balance_after = models.DecimalField(max_digits=12, decimal_places=4)
    description = models.CharField(max_length=255)
    
    # Store exact metrics for complete transparency
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Breakdown: prompt_tokens, completion_tokens, chunks_count, page_count, document_id, session_id"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['payer', '-created_at']),
            models.Index(fields=['organization', '-created_at']),
        ]

    def __str__(self):
        return f"{self.payer.email} | {self.transaction_type} | {self.amount} credits"
