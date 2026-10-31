from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, GlobalConfig
from apps.credits.models import CreditTransaction

@receiver(post_save, sender=User)
def assign_initial_credit(sender, instance, created, **kwargs):
    if created and instance.credit == 0:
        config = GlobalConfig.get_config()
        initial_credit = config.default_user_credit
        instance.credit = initial_credit
        instance.save(update_fields=['credit'])

        CreditTransaction.objects.create(
            payer=instance,
            actor=None,
            transaction_type='INITIAL_SIGNUP',
            amount=initial_credit,
            balance_after=initial_credit,
            description="Initial signup bonus credits",
            metadata={"granted_by": "System"}
        )