import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils import timezone

from apps.users.models import LoginOTP


def issue_login_otp(user):
    code = f"{secrets.randbelow(1_000_000):06d}"
    LoginOTP.objects.filter(user=user, used_at__isnull=True).delete()
    otp = LoginOTP.objects.create(
        user=user,
        code_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    send_mail(
        "Your Luma login verification code",
        f"Your verification code is {code}. It expires in 5 minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
    return otp


def verify_login_otp(user, code):
    otp = LoginOTP.objects.filter(user=user, used_at__isnull=True).first()
    if otp is None or otp.expires_at <= timezone.now():
        return False, "This code has expired. Sign in again to request a new code."
    if otp.attempts >= 5:
        return False, "Too many incorrect codes. Sign in again to request a new code."
    if not check_password(code, otp.code_hash):
        otp.attempts += 1
        otp.save(update_fields=["attempts", "updated_at"])
        return False, "That verification code is incorrect."
    otp.used_at = timezone.now()
    otp.save(update_fields=["used_at", "updated_at"])
    return True, ""