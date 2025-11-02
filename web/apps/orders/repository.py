"""Persistence adapter for storing orders via Django ORM.

This module maps the domain `Order` entity to the Django `OrderModel` and
persists it. It keeps the persistence concerns out of the domain service.
"""

from .models import OrderModel
from .domain import Order, OrderStatus

class OrderRepository:
    """Repository responsible for persisting orders.

    The repository converts the domain `Order` into the Django
    `OrderModel` and persists it, returning the model's primary key.
    """

    def create(self, order: Order):
        """Persist a domain order and return its model id.

        Args:
            order: Domain order to persist. Uses `order.status` (string or
                enum), `total_cents`, `currency`, and optional
                `transaction_id`.

        Returns:
            The primary key of the created `OrderModel` (UUID).
        """
        manager = getattr(OrderModel, "objects")
        obj = manager.create(
            status=order.status.value if isinstance(order.status, OrderStatus) else order.status,
            total_cents=order.total_cents,
            currency=order.currency,
            transaction_id=order.transaction_id,   # Store transaction UUID
        )
        return obj.id

