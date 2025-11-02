"""Inventory service API built with FastAPI.

This module exposes endpoints to check service health and to reserve
inventory for a list of items. Validation is performed with Pydantic
models, while persistence and reservation logic is delegated to the
SQLAlchemy-backed repository in ``repo.InventoryRepo``.
"""

import uuid, logging
import time
from sqlalchemy import text
from repo import InventoryRepo, init_db, engine
from fastapi import Request
from pythonjsonlogger import jsonlogger
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr
from typing import List
from repo import InventoryRepo  # Uses SQLAlchemy and the `inventory-db` database

app = FastAPI(title="Inventory Service")

Sku = constr(pattern=r"^[A-Z0-9_-]{3,32}$")
# logger JSON
logger = logging.getLogger("inventory")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

@app.on_event("startup")
def _startup_db():
    # espera activa breve hasta que la DB acepte conexiones
    deadline = time.time() + 30  # 30s
    while True:
        try:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            break
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(1)
    init_db()

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

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    # guardamos en state para logs locales
    request.state.request_id = rid
    try:
        response = await call_next(request)
    finally:
        # log estructurado mínimo
        logger.info("request handled", extra={"request_id": rid, "path": request.url.path, "method": request.method})
    # devolvemos el header
    response.headers["X-Request-ID"] = rid
    return response