from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Organization, Department

@receiver(post_save, sender=Organization)
def create_default_department(sender, instance, created, **kwargs):
    """Ensure every organization automatically has a default department."""
    if created:
        Department.objects.create(
            organization=instance,
            name="General",
            description="Default department for this organization",
            is_default=True,
            department_manager=instance.manager
        )
