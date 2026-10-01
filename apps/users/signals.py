from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import KYCProfile, LimitProfile
from apps.wallets.models import Wallet


@receiver(post_save, sender=get_user_model())
def create_customer_records(sender, instance, created, **kwargs):
    if created:
        KYCProfile.objects.create(user=instance)
        LimitProfile.objects.create(user=instance)
        Wallet.objects.create(user=instance)