"""Inventory service API built with FastAPI.

This module exposes endpoints to check service health and to reserve
inventory for a list of items. Validation is performed with Pydantic
models, while persistence and reservation logic is delegated to the
SQLAlchemy-backed repository in ``repo.InventoryRepo``.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr
from typing import List
from repo import InventoryRepo  # Uses SQLAlchemy and the `inventory-db` database

app = FastAPI(title="Inventory Service")

Sku = constr(pattern=r"^[A-Z0-9_-]{3,32}$")

class Item(BaseModel):
    """An item to be reserved from inventory.

    Attributes:
        sku: Product SKU matching the allowed pattern.
        quantity: Positive integer quantity to reserve.
    """
    sku: Sku
    quantity: int = Field(gt=0)

class ReserveRequest(BaseModel):
    """Request body for the reserve endpoint.

    Attributes:
        items: List of items (SKU and quantity) to reserve.
    """
    items: List[Item]

class ReserveResponse(BaseModel):
    """Response body for the reserve endpoint.

    Attributes:
        reserved: Whether the reservation succeeded for all items.
        detail: Optional error code when reservation fails.
    """
    reserved: bool
    detail: str | None = None

@app.get("/health")
def health():
    """Liveness/health probe endpoint.

    Returns:
        dict: A small JSON payload indicating service health.
    """
    return {"ok": True}

@app.post("/reserve", response_model=ReserveResponse)
def reserve(req: ReserveRequest):
    """Reserve stock for a batch of items.

    Validates input via Pydantic models, delegates reservation to
    ``InventoryRepo`` which performs a transactional, locked check to
    prevent overselling.

    Args:
        req: The reservation request containing items to reserve.

    Returns:
        ReserveResponse: Response with the `reserved` flag set to True on success.

    Raises:
        HTTPException: With status 422 when any item has insufficient stock.
    """
    items = [(it.sku, it.quantity) for it in req.items]

    ok = InventoryRepo().reserve(items)
    if not ok:
        # Insufficient stock -> 422 with reserved=false
        raise HTTPException(status_code=422, detail={"reserved": False, "detail": "INSUFFICIENT_STOCK"})

    return ReserveResponse(reserved=True)
