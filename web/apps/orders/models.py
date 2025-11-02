import uuid
from django.db import models, transaction

class OrderModel(models.Model):
    # UUID PK expuesto en API
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Contador incremental interno
    internal_id = models.BigIntegerField(unique=True, editable=False, null=True)

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
    transaction_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-internal_id"]

    def save(self, *args, **kwargs):
        # Assign incremental `internal_id` only on creation
        if self.internal_id is None:
            with transaction.atomic():
                last = (
                    OrderModel.objects.select_for_update()
                    .order_by("-internal_id")
                    .first()
                )
                self.internal_id = 1 if not last or last.internal_id is None else last.internal_id + 1

        super().save(*args, **kwargs)
