from django.contrib import admin

from apps.wallets.models import Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("wallet_id", "user", "balance", "currency", "status")
    list_filter = ("status", "currency")
    search_fields = ("user__username", "wallet_id")
    readonly_fields = ("wallet_id", "balance", "created_at", "updated_at")