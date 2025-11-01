from django.urls import path
from .views import OrdersPingView

app_name = "orders"

urlpatterns = [
    path("ping/", OrdersPingView.as_view(), name="ping"),
]
