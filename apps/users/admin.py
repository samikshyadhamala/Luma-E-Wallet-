from django.contrib import admin
from django.utils import timezone

from apps.users.models import KYCProfile, LimitProfile


@admin.register(KYCProfile)
class KYCProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "verified_by", "verified_at")
    list_filter = ("status",)
    search_fields = ("user__username", "full_name", "id_number")
    readonly_fields = ("created_at", "updated_at", "verified_at")

    def save_model(self, request, obj, form, change):
        if obj.status == obj.Status.VERIFIED:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
            obj.rejection_reason = ""
        elif obj.status == obj.Status.REJECTED:
            obj.verified_by = request.user
            obj.verified_at = None
        else:
            obj.verified_by = None
            obj.verified_at = None
        super().save_model(request, obj, form, change)


@admin.register(LimitProfile)
class LimitProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "daily_transfer_limit", "daily_withdrawal_limit")