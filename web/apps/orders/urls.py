from django.urls import path
from .views import OrdersPingView
from .views import OrdersCollectionView, RetrieveOrderView
app_name = "orders"

urlpatterns = [
    path("ping/", OrdersPingView.as_view(), name="ping"),
    path("", OrdersCollectionView.as_view(), name="orders-collection"),  # GET list / POST create
    path("<uuid:oid>/", RetrieveOrderView.as_view(), name="orders-detail"),
]
