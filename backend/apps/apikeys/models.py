import secrets
import hashlib
from django.db import models
from django.conf import settings
from apps.organizations.models import Organization, Department

class OrganizationAPIKey(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='api_keys'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255, help_text="e.g. 'Customer Support Widget'")
    
    # Store first 12 characters for lookup: rag_live_a1b2
    prefix = models.CharField(max_length=16, db_index=True)
    # Store SHA-256 hash of the complete key
    hashed_key = models.CharField(max_length=64, unique=True)

    # Department Scoping
    all_departments = models.BooleanField(
        default=False,
        help_text="If True, queries using this key can access all departments in the organization."
    )
    departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name='scoped_api_keys',
        help_text="Departments accessible by this key when all_departments is False."
    )

    is_active = models.BooleanField(default=True)
    request_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of external queries processed with this API key."
    )
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def generate_key(cls, organization, created_by, name, all_departments=False, department_ids=None):
        """
        Creates an API key. Returns a tuple of (instance, raw_secret_key).
        Raw key is only exposed once during creation.
        """
        raw_secret = f"rag_live_{secrets.token_urlsafe(32)}"
        prefix = raw_secret[:12]
        hashed_key = hashlib.sha256(raw_secret.encode('utf-8')).hexdigest()

        key_obj = cls.objects.create(
            organization=organization,
            created_by=created_by,
            name=name,
            prefix=prefix,
            hashed_key=hashed_key,
            all_departments=all_departments
        )

        if not all_departments and department_ids:
            key_obj.departments.set(department_ids)

        return key_obj, raw_secret

    def get_scoped_department_ids(self) -> list[int]:
        """Returns list of allowed department IDs."""
        if self.all_departments:
            return list(self.organization.departments.values_list('id', flat=True))
        return list(self.departments.values_list('id', flat=True))

    def __str__(self):
        return f"{self.name} ({self.organization.name}) - {self.prefix}..."