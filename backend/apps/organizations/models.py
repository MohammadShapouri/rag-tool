from django.db import models
from django.conf import settings

class Organization(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='org_logos/', null=True, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='managed_organizations'
    )
    staffs = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_organizations',
        blank=True
    )

    # Manager-configurable AI Engine settings
    ai_endpoint = models.CharField(max_length=255, default='http://host.docker.internal')
    ai_port = models.PositiveIntegerField(default=11434)
    ai_api_key = models.CharField(max_length=255, blank=True, null=True)
    ai_model = models.CharField(max_length=100, default='llama3')

    # Organization-level directives and external visibility
    instruction = models.TextField(
        blank=True,
        default='',
        help_text="Custom system instruction and persona for this organization."
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Allows public API key and external widget integration access."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    staffs = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='assigned_departments',
        blank=True
    )
    department_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )
    is_default = models.BooleanField(default=False)
    is_public = models.BooleanField(
        default=True,
        help_text="When true, documents in this department are queryable via external API keys."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'name')

    def __str__(self):
        return f"{self.organization.name} - {self.name}"