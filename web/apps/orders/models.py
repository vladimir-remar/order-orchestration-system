import uuid
from django.db import models

class OrderModel(models.Model):
    # PK public/API (UUID)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ID intern incremental (only for depuration/sort)
    internal_id = models.BigAutoField(unique=True)

    class Status(models.TextChoices):
        CREATED = "CREATED"
        STOCK_RESERVED = "STOCK_RESERVED"
        STOCK_FAILED = "STOCK_FAILED"
        PAID = "PAID"
        PAYMENT_FAILED = "PAYMENT_FAILED"
        CONFIRMED = "CONFIRMED"
        CANCELLED = "CANCELLED"

    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    total_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="EUR")
    transaction_id = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-internal_id"]
