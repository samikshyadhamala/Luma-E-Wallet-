import calendar
from datetime import date, datetime
from io import BytesIO
from uuid import UUID

from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from django.db.models.functions import TruncDay, TruncMonth
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from openpyxl import Workbook

from apps.transactions.forms import AddSavingsForm, AmountForm, BudgetForm, BudgetGoalForm, RefundForm, TransactionFilterForm, TransferForm
from apps.transactions.models import Budget, BudgetGoal, ExpenseCategory, RefundRequest, Transaction
from apps.transactions.services import WalletOperationError, top_up, transfer, withdraw
from apps.wallets.models import Wallet


def _run_operation(request, operation, form, success_message):
    if request.method == "POST" and form.is_valid():
        try:
            operation(form)
        except WalletOperationError as error:
            form.add_error(None, str(error))
        else:
            messages.success(request, success_message)
            return True
    return False


@login_required
@never_cache
def top_up_view(request):
    form = AmountForm(request.POST or None, user=request.user)
    if _run_operation(request, lambda valid_form: top_up(request.user.wallet, valid_form.cleaned_data["amount"], valid_form.cleaned_data["description"], valid_form.cleaned_data["category"], valid_form.cleaned_data["transaction_pin"]), form, "Funds added to your wallet."):
        return redirect("wallets:dashboard")
    return render(request, "transactions/action.html", {"form": form, "title": "Add funds", "eyebrow": "Simulated top-up", "submit_label": "Add funds", "icon": "+", "confirmation_message": "Are you sure you want to add these funds?"})


@login_required
@never_cache
def withdraw_view(request):
    form = AmountForm(request.POST or None, user=request.user)
    if _run_operation(request, lambda valid_form: withdraw(request.user.wallet, valid_form.cleaned_data["amount"], valid_form.cleaned_data["description"], valid_form.cleaned_data["category"], valid_form.cleaned_data["transaction_pin"]), form, "Withdrawal completed."):
        return redirect("wallets:dashboard")
    return render(request, "transactions/action.html", {"form": form, "title": "Withdraw funds", "eyebrow": "Move money out", "submit_label": "Withdraw", "icon": "-", "confirmation_message": "Are you sure you want to withdraw these funds?"})


@login_required
@never_cache
def transfer_view(request):
    sender = request.user.wallet
    form = TransferForm(request.POST or None, user=request.user)

    def do_transfer(valid_form):
        recipient = valid_form.cleaned_data["recipient"]
        receiver = None
        try:
            receiver = Wallet.objects.get(user__username=recipient)
        except Wallet.DoesNotExist:
            try:
                receiver = Wallet.objects.get(wallet_id=UUID(recipient))
            except (Wallet.DoesNotExist, ValueError):
                raise WalletOperationError("We could not find that recipient.")
        if sender.user.kycprofile.status != sender.user.kycprofile.Status.VERIFIED:
            raise WalletOperationError("Complete KYC verification before sending money.")
        transfer(sender, receiver, valid_form.cleaned_data["amount"], valid_form.cleaned_data["description"], valid_form.cleaned_data["category"], valid_form.cleaned_data["transaction_pin"])

    if _run_operation(request, do_transfer, form, "Transfer sent successfully."):
        return redirect("wallets:dashboard")
    return render(request, "transactions/action.html", {"form": form, "title": "Send money", "eyebrow": "Instant wallet transfer", "submit_label": "Send money", "icon": "→", "confirmation_message": "Are you sure you want to send this money?"})


@login_required
def history(request):
    wallet = request.user.wallet
    transactions = Transaction.objects.filter(Q(sender_wallet=wallet) | Q(receiver_wallet=wallet)).distinct()
    filter_form = TransactionFilterForm(request.GET or None, user=request.user)
    if filter_form.is_valid() and filter_form.cleaned_data["status"]:
        transactions = transactions.filter(status=filter_form.cleaned_data["status"])
    if filter_form.is_valid() and filter_form.cleaned_data["category"]:
        transactions = transactions.filter(category=filter_form.cleaned_data["category"])
    return render(request, "transactions/history.html", {"transactions": transactions, "filter_form": filter_form})


def _selected_month(value):
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except (TypeError, ValueError):
        return date.today().replace(day=1)


def _month_offset(month, offset):
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


@login_required
def finance_dashboard(request):
    month = _selected_month(request.GET.get("month"))
    budget_form = BudgetForm(request.POST or None, user=request.user)
    goal_form = BudgetGoalForm(request.POST or None)
    savings_form = AddSavingsForm(request.POST or None)
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "savings":
            goal = get_object_or_404(BudgetGoal, pk=request.POST.get("goal_id"), owner=request.user)
            if savings_form.is_valid():
                amount = savings_form.cleaned_data["amount"]
                remaining = goal.target_amount - goal.saved_amount
                if amount > remaining:
                    savings_form.add_error("amount", f"This goal needs only {remaining:.2f} more.")
                else:
                    with db_transaction.atomic():
                        withdraw(
                            request.user.wallet,
                            amount,
                            f"Goal saving: {goal.name}",
                            ExpenseCategory.objects.filter(owner__isnull=True, name="Other").first(),
                            savings_form.cleaned_data["transaction_pin"],
                        )
                        goal.saved_amount += amount
                        goal.save(update_fields=["saved_amount", "updated_at"])
                    messages.success(request, f"{amount:.2f} saved toward {goal.name}.")
                    return redirect("transactions:finance")
        form = budget_form if form_type == "budget" else goal_form
        if form.is_valid():
            record = form.save(commit=False)
            record.owner = request.user
            record.save()
            messages.success(request, "Budget saved." if form_type == "budget" else "Goal saved.")
            return redirect("transactions:finance")

    wallet = request.user.wallet
    expenses = Transaction.objects.filter(
        sender_wallet=wallet,
        status=Transaction.Status.SUCCESS,
        transaction_type__in=(Transaction.Type.WITHDRAW, Transaction.Type.TRANSFER),
        created_at__year=month.year,
        created_at__month=month.month,
    )
    budgets = list(Budget.objects.filter(owner=request.user, month=month).select_related("category"))
    for budget in budgets:
        budget.spent = expenses.filter(category=budget.category).aggregate(total=Sum("amount"))["total"] or 0
        budget.remaining = max(0, budget.amount - budget.spent)
        budget.percent = min(100, round(float(budget.spent / budget.amount * 100), 1))
        budget.is_over = budget.spent >= budget.amount
        budget.is_near_limit = budget.percent >= 80
    category_totals = list(expenses.values("category__name").annotate(total=Sum("amount")).order_by("-total"))
    total_spent = expenses.aggregate(total=Sum("amount"))["total"] or 0
    monthly_totals = {
        item["period"].date().replace(day=1): item["total"]
        for item in expenses.annotate(period=TruncMonth("created_at")).values("period").annotate(total=Sum("amount"))
    }
    monthly_chart = [{"label": period.strftime("%b"), "total": monthly_totals.get(period, 0)} for period in [_month_offset(month, offset) for offset in range(-5, 1)]]
    daily_totals = {
        item["period"].date().day: item["total"]
        for item in expenses.annotate(period=TruncDay("created_at")).values("period").annotate(total=Sum("amount"))
    }
    daily_chart = [{"label": day, "total": daily_totals.get(day, 0)} for day in range(1, calendar.monthrange(month.year, month.month)[1] + 1)]
    chart_max = max([item["total"] for item in monthly_chart + daily_chart] or [1])
    goals = BudgetGoal.objects.filter(owner=request.user)
    return render(request, "transactions/finance.html", {
        "month": month,
        "month_value": month.strftime("%Y-%m"),
        "budgets": budgets,
        "goals": goals,
        "budget_form": budget_form,
        "goal_form": goal_form,
        "savings_form": savings_form,
        "category_totals": category_totals,
        "total_spent": total_spent,
        "monthly_chart": monthly_chart,
        "daily_chart": daily_chart,
        "chart_max": chart_max,
    })


@login_required
def statement_export(request):
    wallet = request.user.wallet
    transactions = Transaction.objects.filter(Q(sender_wallet=wallet) | Q(receiver_wallet=wallet)).select_related("category").distinct()
    status = request.GET.get("status")
    category_id = request.GET.get("category")
    if status:
        transactions = transactions.filter(status=status)
    if category_id:
        transactions = transactions.filter(category_id=category_id)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Statement"
    sheet.append(["Date", "Transaction ID", "Type", "Category", "Description", "Status", "Amount", "Currency", "Direction"])
    for item in transactions.order_by("-created_at"):
        incoming = item.receiver_wallet_id == wallet.pk
        sheet.append([
            item.created_at.strftime("%Y-%m-%d %H:%M"), str(item.transaction_id), item.get_transaction_type_display(),
            item.category.name if item.category else "Uncategorized", item.description, item.status,
            float(item.amount), item.currency, "Credit" if incoming else "Debit",
        ])
    output = BytesIO()
    workbook.save(output)
    response = HttpResponse(output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="ewallet-statement.xlsx"'
    return response


@login_required
@never_cache
def detail(request, transaction_id):
    wallet = request.user.wallet
    transaction = get_object_or_404(Transaction, transaction_id=transaction_id)
    if wallet not in (transaction.sender_wallet, transaction.receiver_wallet):
        return redirect("transactions:history")
    refund_form = RefundForm()
    existing_refund = transaction.refund_requests.filter(requested_by=request.user).first()
    if request.method == "POST":
        refund_form = RefundForm(request.POST)
        if existing_refund:
            refund_form.add_error(None, "You already have a refund request for this transaction.")
        elif refund_form.is_valid():
            RefundRequest.objects.create(transaction=transaction, requested_by=request.user, **refund_form.cleaned_data)
            messages.success(request, "Refund request submitted for staff review.")
            return redirect("transactions:detail", transaction_id=transaction.transaction_id)
    return render(request, "transactions/detail.html", {"transaction": transaction, "refund_form": refund_form, "existing_refund": existing_refund})


@login_required
@never_cache
def refunds(request):
    requests = RefundRequest.objects.filter(requested_by=request.user).select_related("transaction").order_by("-created_at")
    return render(request, "transactions/refunds.html", {"refunds": requests})