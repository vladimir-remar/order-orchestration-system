"""SQLAlchemy repository for payment transactions.

This module manages persistence for payment transactions using SQLAlchemy and
PostgreSQL. It provides a simple table to record transaction attempts with
their currency, amount, and paid status. It also maintains an internal,
monotonic numeric sequence (internal_id) for ordering and external references.

Database connection parameters are read from the ``DATABASE_URL`` environment
variable, defaulting to a local Postgres URL suitable for development.
"""

import os, uuid
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, Integer, String, Boolean, BigInteger, select
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, mapped_column, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@payments-db:5432/payments")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase):
    pass

class Transaction(Base):
    """SQLAlchemy model representing a payment transaction.

    Attributes:
        id: Public UUID primary key exposed to clients.
        internal_id: Internal monotonically increasing identifier (Stripe-like).
        currency: Three-letter ISO currency code (e.g., EUR, USD).
        amount_cents: Payment amount in minor units (cents).
        paid: Whether the payment succeeded (True) or not (False).
    """

    __tablename__ = "transactions"

    # Public UUID primary key
    id = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Internal incremental id (Stripe style)
    internal_id = mapped_column(BigInteger, unique=True, nullable=True)

    currency = mapped_column(String(3), nullable=False)
    amount_cents = mapped_column(Integer, nullable=False)
    paid = mapped_column(Boolean, default=False, nullable=False)

@contextmanager
def get_session():
    """Yield a SQLAlchemy session bound to the configured engine.

    The session is automatically closed on context exit.

    Yields:
        Session: Active SQLAlchemy session.
    """
    with Session(engine) as s:
        yield s

def _next_internal_id(session: Session) -> int:
    """Compute the next internal_id using a pessimistic lock on the current max.

    A simple row-level lock (``SELECT ... FOR UPDATE``) on the highest
    ``internal_id`` prevents collisions under concurrent writers. This is
    sufficient for demo purposes; production systems may prefer sequences.

    Args:
        session: Open SQLAlchemy session participating in the transaction.

    Returns:
        int: The next internal_id value.
    """
    # Lock the "last" row to avoid collisions (demo-grade approach)
    last = (
        session.execute(
            select(Transaction)
            .order_by(Transaction.internal_id.desc())
            .with_for_update(skip_locked=False)
            .limit(1)
        )
        .scalars()
        .first()
    )
    return 1 if not last or last.internal_id is None else last.internal_id + 1

class PaymentsRepo:
    """Repository for creating and managing payment transactions."""

    def create_tx(self, amount_cents: int, currency: str, paid: bool) -> uuid.UUID:
        """Create and persist a new transaction.

        The method first computes the next ``internal_id`` atomically, then
        stores the transaction row and returns the public UUID.

        Args:
            amount_cents: Payment amount in minor currency units (cents).
            currency: Three-letter ISO currency code (e.g., EUR, USD).
            paid: Whether the payment was successful.

        Returns:
            uuid.UUID: The public UUID of the created transaction.
        """
        with get_session() as s:
            # Compute internal_id atomically
            nid = _next_internal_id(s)
            tx = Transaction(
                internal_id=nid,
                amount_cents=amount_cents,
                currency=currency,
                paid=paid,
            )
            s.add(tx)
            s.commit()
            return tx.id  # UUID

Base.metadata.create_all(engine)