from django.urls import path

from apps.staff_operations import views

app_name = "staff_operations"

urlpatterns = [
	path("", views.dashboard, name="dashboard"),
	path("kyc/", views.kyc_review, name="kyc_review"),
	path("risk/", views.risk_review, name="risk_review"),
	path("refunds/", views.refund_review, name="refund_review"),
	path("wallets/", views.wallet_review, name="wallet_review"),
	path("users/", views.user_review, name="user_review"),
	path("logout/", views.staff_logout, name="logout"),
]