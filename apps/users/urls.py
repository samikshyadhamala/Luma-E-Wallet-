from django.contrib.auth.views import LogoutView
from django.urls import path

from apps.users import views

app_name = "users"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("kyc/", views.kyc, name="kyc"),
    path("profile/", views.profile, name="profile"),
    path("initial-pin/", views.initial_pin, name="initial_pin"),
]