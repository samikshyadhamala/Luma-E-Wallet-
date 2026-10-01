from django.urls import path

from apps.wallets import views

app_name = "wallets"

urlpatterns = [
    path("news/", views.news, name="news"),
    path("news/feed/", views.news_feed, name="news_feed"),
    path("", views.dashboard, name="dashboard"),
]