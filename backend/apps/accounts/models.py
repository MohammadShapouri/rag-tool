from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Custom manager where email is the unique identifier for authentication.
    Does not reference or require 'is_staff'.
    """
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        if not username:
            raise ValueError('A username is required.')

        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model without an 'is_staff' database column.
    
    Roles:
      - Superuser: has is_superuser=True; can access Django Admin and Superuser panel.
      - Manager: Organization owner; manages depts, staff, docs, and AI endpoints.
      - Staff: Assigned to organization and/or department(s) with scoped querying access.
    """
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    email = models.EmailField(unique=True, db_index=True)
    is_active = models.BooleanField(default=True)

    # 4-decimal precision for token- and chunk-weighted micro-billing
    credit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="Available credits for RAG querying and document processing."
    )
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    @property
    def is_staff(self):
        """
        Dynamic property that satisfies Django Admin's internal
        AdminSite.has_permission(request) check (request.user.is_staff)
        without storing an 'is_staff' column in the database table.
        """
        return self.is_active and self.is_superuser

    def __str__(self):
        return f"{self.email} ({self.username})"


class GlobalConfig(models.Model):
    """
    System-wide singleton configuration managed exclusively by Superusers.
    Defines default credits granted to new accounts upon registration.
    """
    default_user_credit = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal('100.0000'),
        help_text="Default credits automatically allocated to newly registered users."
    )
    allow_signup = models.BooleanField(
        default=True,
        help_text="Toggle whether public registrations are permitted."
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Global System Configuration'
        verbose_name_plural = 'Global System Configuration'

    def save(self, *args, **kwargs):
        # Enforce singleton pattern (always row id=1)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'default_user_credit': Decimal('100.0000'),
                'allow_signup': True
            }
        )
        return config

    def __str__(self):
        return f"Global Configuration (Default Signup Credit: {self.default_user_credit})"
