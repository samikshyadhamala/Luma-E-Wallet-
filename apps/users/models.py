from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class KYCProfile(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=160, blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    id_number = models.CharField(max_length=80, blank=True)
    document = models.FileField(upload_to="kyc_documents/", blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    rejection_reason = models.TextField(blank=True)
    transaction_pin_hash = models.CharField(max_length=128, blank=True)
    transaction_pin_failed_attempts = models.PositiveSmallIntegerField(default=0)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_kyc_profiles",
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.status})"


class LimitProfile(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    daily_transfer_limit = models.DecimalField(max_digits=12, decimal_places=2, default=1000)
    daily_withdrawal_limit = models.DecimalField(max_digits=12, decimal_places=2, default=1000)

    def __str__(self):
        return f"Limits for {self.user.username}"


class LoginOTP(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="login_otps")
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)