from django.db import models
from django.conf import settings
from apps.organizations.models import Organization, Department

class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_sessions'
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='chat_sessions'
    )
    selected_departments = models.ManyToManyField(
        Department,
        related_name='chat_sessions',
        blank=True
    )
    title = models.CharField(max_length=255, default='New Conversation')
    
    # Deterministic session identifier for external integrations
    external_session_key = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique session identifier for third-party websites and widgets."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            # Prevents race conditions during get_or_create on concurrent external requests
            models.UniqueConstraint(
                fields=['organization', 'external_session_key'],
                name='unique_org_external_session',
                condition=models.Q(external_session_key__isnull=False)
            )
        ]

    def __str__(self):
        return f"{self.title} ({self.organization.name})"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )

    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=15, choices=ROLE_CHOICES)
    content = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    
    # Stores billing breakdown, token metrics, and API key origins
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:40]}"
