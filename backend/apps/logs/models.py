from django.db import models
from django.conf import settings
from apps.organizations.models import Organization

class AuditLog(models.Model):
    SOURCE_CHOICES = (
        ('internal_chat', 'Internal Chat'),
        ('public_api_key', 'Public API Key'),
    )
    STATUS_CHOICES = (
        ('SUCCESS', 'Success'),
        ('ERROR', 'Error'),
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    department_ids = models.JSONField(default=list, blank=True)
    department_names = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES)

    # Actor information
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='query_audit_logs'
    )
    api_key_name = models.CharField(max_length=255, blank=True, null=True)
    api_key_preview = models.CharField(max_length=64, blank=True, null=True)

    # Query & Synthesis
    query = models.TextField()
    response = models.TextField(blank=True, default='')
    latency_ms = models.PositiveIntegerField(default=0)
    tokens_used = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESS')
    error_message = models.TextField(blank=True, null=True)

    # Superuser Deep Diagnostics
    vectordb_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Telemetry: collection_name, vector_dimensions, top_k, similarity_scores, latencies."
    )
    database_details = models.JSONField(
        default=dict,
        blank=True,
        help_text="Database metrics: query counts, latencies, credit balances."
    )

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['organization', '-timestamp']),
            models.Index(fields=['source', '-timestamp']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.organization.name} ({self.source}) - {self.status}"