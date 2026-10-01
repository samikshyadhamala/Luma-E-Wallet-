from django.urls import path

from apps.transactions import views

app_name = "transactions"

urlpatterns = [
    path("top-up/", views.top_up_view, name="top_up"),
    path("withdraw/", views.withdraw_view, name="withdraw"),
    path("send-money/", views.transfer_view, name="transfer"),
    path("finance/", views.finance_dashboard, name="finance"),
    path("statement.xlsx", views.statement_export, name="statement_export"),
    path("", views.history, name="history"),
    path("refunds/", views.refunds, name="refunds"),
    path("<uuid:transaction_id>/", views.detail, name="detail"),
]