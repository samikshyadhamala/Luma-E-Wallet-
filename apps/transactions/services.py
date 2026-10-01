from decimal import Decimal
from functools import wraps
from inspect import signature

from django.contrib.auth.hashers import check_password
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.transactions.models import LedgerEntry, RefundRequest, Transaction
from apps.transactions.fraud import assess_transaction
from apps.transactions.notifications import send_transaction_email
from apps.wallets.models import Wallet


class WalletOperationError(Exception):
    pass


def _check_amount(amount):
    amount = Decimal(str(amount))
    if amount <= 0:
        raise WalletOperationError("Amount must be greater than zero.")
    return amount


def _check_active(wallet):
    if wallet.status != Wallet.Status.ACTIVE:
        raise WalletOperationError("This wallet is not active.")


def _check_verified(wallet):
    if wallet.user.kycprofile.status != "VERIFIED":
        raise WalletOperationError("Complete identity verification before making transactions.")


def _check_pin(wallet, pin):
    user = wallet.user
    profile = user.kycprofile
    if not user.is_active:
        raise WalletOperationError("This account is suspended. Contact support.")
    if not profile.transaction_pin_hash:
        raise WalletOperationError("Set a transaction PIN in your profile before making payments.")
    if not pin or not check_password(pin, profile.transaction_pin_hash):
        profile.transaction_pin_failed_attempts += 1
        if profile.transaction_pin_failed_attempts >= 5:
            user.is_active = False
            user.save(update_fields=["is_active"])
            profile.save(update_fields=["transaction_pin_failed_attempts", "updated_at"])
            raise WalletOperationError("Too many incorrect PIN attempts. Your account has been suspended.")
        profile.save(update_fields=["transaction_pin_failed_attempts", "updated_at"])
        if profile.transaction_pin_failed_attempts >= 3:
            remaining = 5 - profile.transaction_pin_failed_attempts
            raise WalletOperationError(f"Incorrect PIN. Warning: {remaining} attempt(s) remaining before account suspension.")
        raise WalletOperationError("The transaction PIN is incorrect.")
    if profile.transaction_pin_failed_attempts:
        profile.transaction_pin_failed_attempts = 0
        profile.save(update_fields=["transaction_pin_failed_attempts", "updated_at"])


def _pin_required(operation):
    operation_signature = signature(operation)

    @wraps(operation)
    def wrapped(*args, **kwargs):
        bound = operation_signature.bind_partial(*args, **kwargs)
        wallet = bound.arguments.get("wallet") or bound.arguments.get("sender")
        _check_pin(wallet, bound.arguments.get("pin"))
        return operation(*args, **kwargs)

    return wrapped


def _complete(transaction_record, wallet, entry_type, amount):
    before = wallet.balance
    after = before + amount if entry_type == LedgerEntry.EntryType.CREDIT else before - amount
    if after < 0:
        raise WalletOperationError("Insufficient balance.")
    wallet.balance = after
    wallet.save(update_fields=["balance", "updated_at"])
    LedgerEntry.objects.create(
        transaction=transaction_record,
        wallet=wallet,
        entry_type=entry_type,
        amount=amount,
        balance_before=before,
        balance_after=after,
    )


def _apply_risk_review(record):
    risk_status, risk_score, risk_reason = assess_transaction(
        record.transaction_type,
        record.amount,
        record.receiver_wallet,
    )
    record.risk_status = risk_status
    record.risk_score = risk_score
    record.risk_reason = risk_reason


@_pin_required
@db_transaction.atomic
def top_up(wallet, amount, description="Simulated top-up", category=None, pin=None):
    amount = _check_amount(amount)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    _check_active(wallet)
    _check_verified(wallet)
    record = Transaction.objects.create(
        transaction_type=Transaction.Type.TOP_UP,
        amount=amount,
        currency=wallet.currency,
        receiver_wallet=wallet,
        category=category,
        description=description,
    )
    _apply_risk_review(record)
    _complete(record, wallet, LedgerEntry.EntryType.CREDIT, amount)
    record.status = Transaction.Status.SUCCESS
    record.processed_at = timezone.now()
    record.save(update_fields=["status", "risk_status", "risk_score", "risk_reason", "processed_at", "updated_at"])
    db_transaction.on_commit(lambda: send_transaction_email(record))
    return record


@_pin_required
@db_transaction.atomic
def withdraw(wallet, amount, description="Simulated withdrawal", category=None, pin=None):
    amount = _check_amount(amount)
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    _check_active(wallet)
    _check_verified(wallet)
    record = Transaction.objects.create(
        transaction_type=Transaction.Type.WITHDRAW,
        amount=amount,
        currency=wallet.currency,
        sender_wallet=wallet,
        category=category,
        description=description,
    )
    _apply_risk_review(record)
    _complete(record, wallet, LedgerEntry.EntryType.DEBIT, amount)
    record.status = Transaction.Status.SUCCESS
    record.processed_at = timezone.now()
    record.save(update_fields=["status", "risk_status", "risk_score", "risk_reason", "processed_at", "updated_at"])
    db_transaction.on_commit(lambda: send_transaction_email(record))
    return record


@_pin_required
@db_transaction.atomic
def transfer(sender, receiver, amount, description="Wallet transfer", category=None, pin=None):
    amount = _check_amount(amount)
    if sender.pk == receiver.pk:
        raise WalletOperationError("Sender and receiver must be different.")
    wallets = {
        wallet.pk: wallet
        for wallet in Wallet.objects.select_for_update().filter(pk__in=[sender.pk, receiver.pk])
    }
    sender = wallets[sender.pk]
    receiver = wallets[receiver.pk]
    _check_active(sender)
    _check_active(receiver)
    _check_verified(sender)
    _check_verified(receiver)
    record = Transaction.objects.create(
        transaction_type=Transaction.Type.TRANSFER,
        amount=amount,
        currency=sender.currency,
        sender_wallet=sender,
        receiver_wallet=receiver,
        category=category,
        description=description,
    )
    _apply_risk_review(record)
    _complete(record, sender, LedgerEntry.EntryType.DEBIT, amount)
    _complete(record, receiver, LedgerEntry.EntryType.CREDIT, amount)
    record.status = Transaction.Status.SUCCESS
    record.processed_at = timezone.now()
    record.save(update_fields=["status", "risk_status", "risk_score", "risk_reason", "processed_at", "updated_at"])
    db_transaction.on_commit(lambda: send_transaction_email(record))
    return record


@db_transaction.atomic
def approve_refund(refund_request, reviewer):
    """Credit the customer once and create the auditable refund transaction."""
    refund_request = RefundRequest.objects.select_for_update().select_related("requested_by__wallet").get(pk=refund_request.pk)
    if refund_request.refund_transaction_id:
        return refund_request.refund_transaction
    if refund_request.status != RefundRequest.Status.APPROVED:
        raise WalletOperationError("Only an approved refund can be completed.")

    wallet = Wallet.objects.select_for_update().get(user=refund_request.requested_by)
    _check_active(wallet)
    _check_verified(wallet)
    record = Transaction.objects.create(
        transaction_type=Transaction.Type.REFUND,
        status=Transaction.Status.SUCCESS,
        amount=refund_request.transaction.amount,
        currency=wallet.currency,
        receiver_wallet=wallet,
        category=refund_request.transaction.category,
        description=f"Refund for {refund_request.transaction.transaction_id}",
        risk_status=Transaction.RiskStatus.CLEAR,
        risk_reason="Approved by operations staff",
        processed_at=timezone.now(),
    )
    _complete(record, wallet, LedgerEntry.EntryType.CREDIT, record.amount)
    refund_request.refund_transaction = record
    refund_request.status = RefundRequest.Status.COMPLETED
    refund_request.reviewed_by = reviewer
    refund_request.reviewed_at = timezone.now()
    refund_request.save(update_fields=["refund_transaction", "status", "reviewed_by", "reviewed_at", "updated_at"])
    db_transaction.on_commit(lambda: send_transaction_email(record))
    return record