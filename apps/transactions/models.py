import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel
from apps.wallets.models import Wallet


class ExpenseCategory(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="expense_categories",
    )
    name = models.CharField(max_length=80)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=("owner", "name"), name="unique_expense_category_per_owner"),
        ]

    def __str__(self):
        return self.name


class Transaction(TimeStampedModel):
    class Type(models.TextChoices):
        TOP_UP = "TOP_UP", "Top up"
        WITHDRAW = "WITHDRAW", "Withdraw"
        TRANSFER = "TRANSFER", "Transfer"
        REFUND = "REFUND", "Refund"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        REJECTED = "REJECTED", "Rejected"

    class RiskStatus(models.TextChoices):
        NOT_REVIEWED = "NOT_REVIEWED", "Not reviewed"
        CLEAR = "CLEAR", "Clear"
        FLAGGED = "FLAGGED", "Flagged for review"
        BLOCKED = "BLOCKED", "Blocked"

    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    risk_status = models.CharField(max_length=12, choices=RiskStatus.choices, default=RiskStatus.NOT_REVIEWED)
    risk_score = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    risk_reason = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_transactions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    currency = models.CharField(max_length=3, default="NPR")
    category = models.ForeignKey(
        ExpenseCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="transactions",
    )
    sender_wallet = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.PROTECT, related_name="sent_transactions")
    receiver_wallet = models.ForeignKey(Wallet, null=True, blank=True, on_delete=models.PROTECT, related_name="received_transactions")
    description = models.CharField(max_length=255, blank=True)
    failure_reason = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return str(self.transaction_id)


class Budget(TimeStampedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name="budgets")
    month = models.DateField(help_text="Use the first day of the budget month.")
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])

    class Meta:
        ordering = ("-month", "category__name")
        constraints = [
            models.UniqueConstraint(fields=("owner", "category", "month"), name="unique_budget_per_category_month"),
        ]

    def __str__(self):
        return f"{self.owner} - {self.category} - {self.month:%Y-%m}"


class BudgetGoal(TimeStampedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budget_goals")
    name = models.CharField(max_length=120)
    target_amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    saved_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    target_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("target_date", "-created_at")

    @property
    def progress_percent(self):
        if not self.target_amount:
            return 0
        return min(100, round(float(self.saved_amount / self.target_amount * 100), 1))

    @property
    def is_completed(self):
        return self.saved_amount >= self.target_amount


class LedgerEntry(TimeStampedModel):
    class EntryType(models.TextChoices):
        DEBIT = "DEBIT", "Debit"
        CREDIT = "CREDIT", "Credit"

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="ledger_entries")
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_type = models.CharField(max_length=6, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)])
    balance_before = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)


class RefundRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        COMPLETED = "COMPLETED", "Completed"

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="refund_requests")
    refund_transaction = models.OneToOneField(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="source_refund_request",
    )
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="refund_requests")
    reason = models.TextField()
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_refunds")
    staff_comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)