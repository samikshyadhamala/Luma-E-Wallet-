from django.contrib import admin
from django.utils import timezone

from apps.transactions.models import Budget, BudgetGoal, ExpenseCategory, LedgerEntry, RefundRequest, Transaction
from apps.transactions.services import WalletOperationError, approve_refund


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "transaction_type", "amount", "status", "risk_status", "created_at")
    list_filter = ("transaction_type", "status", "risk_status", "currency")
    search_fields = ("transaction_id", "sender_wallet__user__username", "receiver_wallet__user__username")
    readonly_fields = tuple(
        field.name for field in Transaction._meta.fields
        if field.name not in {"risk_status", "risk_reason", "reviewed_by", "reviewed_at"}
    )
    actions = ("mark_clear", "mark_flagged", "mark_blocked")

    @admin.action(description="Mark selected transactions as clear")
    def mark_clear(self, request, queryset):
        queryset.update(
            risk_status=Transaction.RiskStatus.CLEAR,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Flag selected transactions for review")
    def mark_flagged(self, request, queryset):
        queryset.update(
            risk_status=Transaction.RiskStatus.FLAGGED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Block selected transactions")
    def mark_blocked(self, request, queryset):
        queryset.update(
            risk_status=Transaction.RiskStatus.BLOCKED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("transaction", "wallet", "entry_type", "amount", "balance_after")
    readonly_fields = tuple(field.name for field in LedgerEntry._meta.fields)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("transaction", "requested_by", "status", "refund_transaction", "reviewed_by", "created_at")
    list_filter = ("status",)
    search_fields = ("transaction__transaction_id", "requested_by__username")
    readonly_fields = ("created_at", "updated_at", "reviewed_at", "refund_transaction")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.status == RefundRequest.Status.APPROVED and not obj.refund_transaction_id:
            try:
                approve_refund(obj, request.user)
            except WalletOperationError as error:
                self.message_user(request, str(error), level="error")


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "created_at")
    list_filter = ("owner",)
    search_fields = ("name", "owner__username")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("owner", "category", "month", "amount")
    list_filter = ("month", "category")
    search_fields = ("owner__username", "category__name")


@admin.register(BudgetGoal)
class BudgetGoalAdmin(admin.ModelAdmin):
    list_display = ("owner", "name", "target_amount", "saved_amount", "target_date")
    search_fields = ("owner__username", "name")