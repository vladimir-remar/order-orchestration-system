from django.urls import path
from .api import health_view

urlpatterns = [
    path("health/", health_view, name="health"),
]
