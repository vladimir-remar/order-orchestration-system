from django.urls import path
from .views import OrdersPingView
from .views import OrdersPingView, CreateOrderView

app_name = "orders"

urlpatterns = [
    path("ping/", OrdersPingView.as_view(), name="ping"),
    path("", CreateOrderView.as_view(), name="create"),  # POST /api/orders/
]
