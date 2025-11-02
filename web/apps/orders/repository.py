"""Repository layer for persisting orders.

This module contains a small repository abstraction used by the
application to persist order information. It intentionally keeps a
thin interface so the domain layer is not coupled to Django ORM
details.
"""

from .models import OrderModel
from .domain import Order, OrderStatus


class OrderRepository:
    """Repository that persists Order domain objects using Django ORM.

    The repository exposes a minimal API that returns primitive values
    (for example the persisted object's id) to keep domain code
    decoupled from ORM types.
    """

    def create(self, order: Order, transaction_id: int | None = None):
        """Persist a new order record.

        The method maps fields from the domain `Order` into the
        `OrderModel` and returns the created model's identifier.

        Args:
            order: Domain `Order` instance to persist.
            transaction_id: Optional transaction identifier returned by
                the payments service (if available).

        Returns:
            The persisted `OrderModel` primary key (UUID or integer
            depending on the model configuration).
        """
        obj = OrderModel.objects.create(
            status=order.status.value if isinstance(order.status, OrderStatus) else order.status,
            total_cents=order.total_cents,
            currency=order.currency,
            transaction_id=transaction_id,
        )
        return obj.id  # <-- UUID
