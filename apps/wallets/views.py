from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from apps.transactions.models import Transaction
from apps.wallets.news import get_news


@login_required
def dashboard(request):
    wallet = request.user.wallet
    transactions = Transaction.objects.filter(
        sender_wallet=wallet
    ) | Transaction.objects.filter(receiver_wallet=wallet)
    transactions = transactions.select_related("category").distinct()
    recent_transactions = transactions.order_by("-created_at")[:8]
    today = timezone.localdate()
    month_start = today.replace(day=1)
    current = transactions.filter(status=Transaction.Status.SUCCESS, created_at__year=today.year, created_at__month=today.month)
    outgoing = current.filter(sender_wallet=wallet).aggregate(total=Sum("amount"))["total"] or 0
    incoming = current.filter(receiver_wallet=wallet).aggregate(total=Sum("amount"))["total"] or 0
    type_breakdown = list(current.values("transaction_type").annotate(count=Count("id"), total=Sum("amount")).order_by("-count"))
    monthly_chart = []
    for offset in range(-5, 1):
        period = _month_offset(month_start, offset)
        month_transactions = transactions.filter(status=Transaction.Status.SUCCESS, created_at__year=period.year, created_at__month=period.month)
        monthly_chart.append({
            "label": period.strftime("%b"),
            "income": month_transactions.filter(receiver_wallet=wallet).aggregate(total=Sum("amount"))["total"] or 0,
            "spending": month_transactions.filter(sender_wallet=wallet).aggregate(total=Sum("amount"))["total"] or 0,
        })
    chart_max = max([max(item["income"], item["spending"]) for item in monthly_chart] or [1])
    return render(request, "wallets/dashboard.html", {
        "wallet": wallet,
        "recent_transactions": recent_transactions,
        "current_month": month_start,
        "monthly_spending": outgoing,
        "monthly_income": incoming,
        "monthly_count": current.count(),
        "type_breakdown": type_breakdown,
        "monthly_chart": monthly_chart,
        "chart_max": chart_max,
    })


@login_required
def news(request):
    return render(request, "wallets/news.html")


@login_required
def news_feed(request):
    return JsonResponse(get_news())


def _month_offset(month, offset):
    index = month.year * 12 + month.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)