from django.contrib import messages
from functools import wraps

from django.contrib.auth import get_user_model, logout
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.transactions.models import RefundRequest, Transaction
from apps.transactions.services import WalletOperationError, approve_refund
from apps.users.models import KYCProfile
from apps.wallets.models import Wallet


STAFF_LOGIN = "/account/login/"


def _staff(view):
    @wraps(view)
    def protected_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), STAFF_LOGIN)
        if not request.user.is_active or not request.user.is_staff:
            return render(request, "staff_operations/forbidden.html", status=403)
        return view(request, *args, **kwargs)

    return protected_view


@_staff
def dashboard(request):
    pending_kyc = KYCProfile.objects.filter(status=KYCProfile.Status.PENDING).select_related("user").order_by("created_at")
    flagged_transactions = Transaction.objects.filter(risk_status=Transaction.RiskStatus.FLAGGED).select_related("sender_wallet__user", "receiver_wallet__user").order_by("-created_at")
    pending_refunds = RefundRequest.objects.filter(status=RefundRequest.Status.PENDING).select_related("requested_by", "transaction").order_by("created_at")
    recent_transactions = Transaction.objects.select_related("sender_wallet__user", "receiver_wallet__user").order_by("-created_at")[:8]
    return render(request, "staff_operations/dashboard.html", {
        "user_count": get_user_model().objects.filter(is_staff=False, is_superuser=False).count(),
        "wallet_count": Wallet.objects.count(), "pending_kyc": pending_kyc[:8], "pending_kyc_count": pending_kyc.count(),
        "flagged_transactions": flagged_transactions[:8], "flagged_count": flagged_transactions.count(),
        "pending_refunds": pending_refunds[:8], "pending_refund_count": pending_refunds.count(), "recent_transactions": recent_transactions,
    })


@_staff
def kyc_review(request):
    profiles = KYCProfile.objects.select_related("user", "verified_by").order_by("status", "-created_at")
    selected = request.GET.get("user")
    profile = get_object_or_404(KYCProfile.objects.select_related("user", "verified_by"), pk=selected) if selected else None
    if profile and request.method == "POST":
        action = request.POST.get("action")
        if action == "verify":
            profile.status = KYCProfile.Status.VERIFIED
            profile.verified_by = request.user
            profile.verified_at = timezone.now()
            profile.rejection_reason = ""
            messages.success(request, "KYC profile verified.")
        elif action == "reject":
            profile.status = KYCProfile.Status.REJECTED
            profile.verified_by = request.user
            profile.verified_at = None
            profile.rejection_reason = request.POST.get("reason", "Rejected during manual review.")
            messages.success(request, "KYC profile rejected.")
        profile.save()
        return redirect(f"/admin/kyc/?user={profile.pk}")
    return render(request, "staff_operations/queue.html", {"eyebrow": "Identity operations", "title": "KYC review", "description": "Verify customer identity before allowing wallet transactions.", "queue_type": "kyc", "profiles": profiles, "detail_profile": profile})


@_staff
def risk_review(request):
    transactions = Transaction.objects.select_related("sender_wallet__user", "receiver_wallet__user").order_by("risk_status", "-created_at")
    selected = request.GET.get("transaction")
    record = get_object_or_404(Transaction, pk=selected) if selected else None
    if record and request.method == "POST":
        status = request.POST.get("risk_status")
        if status in Transaction.RiskStatus.values:
            record.risk_status = status
            record.reviewed_by = request.user
            record.reviewed_at = timezone.now()
            record.risk_reason = request.POST.get("risk_reason", record.risk_reason)
            record.save(update_fields=["risk_status", "reviewed_by", "reviewed_at", "risk_reason", "updated_at"])
            messages.success(request, "Risk decision saved.")
        return redirect(f"/admin/risk/?transaction={record.pk}")
    return render(request, "staff_operations/queue.html", {"eyebrow": "Trust & safety", "title": "Risk review", "description": "Review flagged activity and record a clear, flagged, or blocked decision.", "queue_type": "risk", "transactions": transactions, "detail_transaction": record})


@_staff
def refund_review(request):
    refunds = RefundRequest.objects.select_related("requested_by", "transaction").order_by("status", "-created_at")
    selected = request.GET.get("refund")
    refund = get_object_or_404(RefundRequest.objects.select_related("requested_by", "transaction"), pk=selected) if selected else None
    if refund and request.method == "POST":
        action = request.POST.get("action")
        if action == "approve" and refund.status == RefundRequest.Status.PENDING:
            refund.status = RefundRequest.Status.APPROVED
            refund.reviewed_by = request.user
            refund.reviewed_at = timezone.now()
            refund.staff_comment = request.POST.get("staff_comment", "")
            refund.save(update_fields=["status", "reviewed_by", "reviewed_at", "staff_comment", "updated_at"])
            try:
                approve_refund(refund, request.user)
                messages.success(request, "Refund approved and completed.")
            except WalletOperationError as error:
                messages.error(request, str(error))
        elif action == "reject" and refund.status == RefundRequest.Status.PENDING:
            refund.status = RefundRequest.Status.REJECTED
            refund.reviewed_by = request.user
            refund.reviewed_at = timezone.now()
            refund.staff_comment = request.POST.get("staff_comment", "")
            refund.save(update_fields=["status", "reviewed_by", "reviewed_at", "staff_comment", "updated_at"])
            messages.success(request, "Refund rejected.")
        return redirect(f"/admin/refunds/?refund={refund.pk}")
    return render(request, "staff_operations/queue.html", {"eyebrow": "Customer care", "title": "Refund review", "description": "Approve, reject, and complete customer refund requests.", "queue_type": "refunds", "refunds": refunds, "detail_refund": refund})


@_staff
def wallet_review(request):
    wallets = Wallet.objects.select_related("user").order_by("status", "-updated_at")
    selected = request.GET.get("wallet")
    wallet = get_object_or_404(Wallet.objects.select_related("user"), pk=selected) if selected else None
    if wallet and request.method == "POST":
        status = request.POST.get("status")
        if status in Wallet.Status.values:
            wallet.status = status
            wallet.save(update_fields=["status", "updated_at"])
            messages.success(request, "Wallet status updated.")
        return redirect(f"/admin/wallets/?wallet={wallet.pk}")
    return render(request, "staff_operations/queue.html", {"eyebrow": "Account controls", "title": "Wallets", "description": "Inspect balances and manage active, frozen, or closed wallet access.", "queue_type": "wallets", "wallets": wallets, "detail_wallet": wallet})


@_staff
def user_review(request):
    users = get_user_model().objects.order_by("-date_joined")
    selected = request.GET.get("user")
    account = get_object_or_404(get_user_model(), pk=selected) if selected else None
    if account and request.method == "POST":
        if account.pk == request.user.pk:
            messages.error(request, "You cannot suspend your own staff account.")
        else:
            account.is_active = request.POST.get("action") == "activate"
            account.save(update_fields=["is_active"])
            messages.success(request, "User access updated.")
        return redirect(f"/admin/users/?user={account.pk}")
    return render(request, "staff_operations/queue.html", {"eyebrow": "Access management", "title": "Users & roles", "description": "Manage customer access and account status.", "queue_type": "users", "users": users, "detail_account": account})


@_staff
def staff_logout(request):
    logout(request)
    return redirect("users:login")
