from django.db import models
from django.conf import settings
from apps.organizations.models import Department

class Document(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('READY', 'Ready'),
        ('FAILED', 'Failed'),
    )

    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='documents')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    file = models.FileField(upload_to='department_docs/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, null=True)

    # Ingestion metadata metrics
    chunk_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of text chunks created from this document."
    )
    vector_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of vector points successfully indexed into Qdrant."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.department.name})"