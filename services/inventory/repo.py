"""SQLAlchemy repository for managing stock inventory.

This module provides database persistence for stock quantities using SQLAlchemy and
PostgreSQL. It supports basic inventory operations like checking stock levels,
updating quantities, and atomically reserving items with pessimistic locking.

The schema consists of a single 'stock' table mapping SKUs to their available
quantity. Database connection parameters are configured via DATABASE_URL env var.
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, Integer, String
from sqlalchemy.orm import DeclarativeBase, mapped_column, Session

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@inventory-db:5432/inventory")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

class Base(DeclarativeBase): pass

class Stock(Base):
    """SQLAlchemy model representing available stock for a product.

    Attributes:
        sku: Product SKU (string, max 64 chars) used as primary key.
        quantity: Available quantity in stock (integer, non-null, defaults to 0).
    """
    __tablename__ = "stock"
    sku = mapped_column(String(64), primary_key=True)
    quantity = mapped_column(Integer, nullable=False, default=0)

def init_db():
    # crea tablas si no existen
    Base.metadata.create_all(engine)

@contextmanager
def get_session():
    """Context manager that yields a SQLAlchemy session.

    The session is automatically closed when exiting the context.

    Yields:
        Session: Active SQLAlchemy session connected to the database.
    """
    with Session(engine) as s:
        yield s

class InventoryRepo:
    """Repository class for inventory operations.

    Provides methods for checking stock levels, updating quantities,
    and atomically reserving items while preventing overselling.
    """

    def get(self, sku: str) -> int:
        """Get current stock quantity for a SKU.

        Args:
            sku: Product SKU to look up.

        Returns:
            int: Current available quantity (0 if SKU not found).
        """
        with get_session() as s:
            obj = s.get(Stock, sku)
            return obj.quantity if obj else 0

    def upsert(self, sku: str, quantity: int) -> None:
        """Set stock quantity for a SKU, creating if it doesn't exist.

        Args:
            sku: Product SKU to update.
            quantity: New quantity value to set.
        """
        with get_session() as s:
            obj = s.get(Stock, sku) or Stock(sku=sku, quantity=0)
            obj.quantity = quantity
            s.merge(obj)
            s.commit()

    def reserve(self, items: list[tuple[str, int]]) -> bool:
        """Atomically reserve quantities for multiple SKUs.

        Uses SELECT FOR UPDATE to prevent concurrent reservations.
        Either reserves all items or none (rolls back on insufficient stock).

        Args:
            items: List of (sku, quantity) tuples to reserve.

        Returns:
            bool: True if all items were reserved, False if any had
                insufficient stock (no changes made in that case).
        """
        with get_session() as s:
            rows = s.query(Stock).filter(Stock.sku.in_([sku for sku, _ in items])).with_for_update().all()
            current = {r.sku: r.quantity for r in rows}
            for sku, qty in items:
                if current.get(sku, 0) < qty:
                    s.rollback()
                    return False
            for r in rows:
                dec = dict(items)[r.sku]
                r.quantity -= dec
            s.commit()
            return True
