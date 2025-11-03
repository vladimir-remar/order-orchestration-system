"""Payments service API built with FastAPI.

This module exposes endpoints to check service health and to charge a
payment. Validation is performed with Pydantic models, while persistence
is delegated to the SQLAlchemy-backed repository in ``repo.PaymentsRepo``.
"""

import uuid
import logging
import time
from sqlalchemy import text
from repo import engine

from fastapi import Request
from pythonjsonlogger import jsonlogger

from fastapi import FastAPI, HTTPException, Header
from typing import Annotated, Optional
from repo import PaymentsRepo, IdempotencyKey, canonical_hash, get_session, Transaction
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, constr



app = FastAPI(title="Payments Service")

Currency = constr(pattern=r"^[A-Z]{3}$")

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


logger = logging.getLogger("payments")
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)
class ChargeRequest(BaseModel):
    """Request body for the charge endpoint.

    Attributes:
        amount_cents: Positive payment amount in minor currency units (cents).
        currency: Three-letter ISO currency code (e.g., EUR, USD).
    """
    amount_cents: int = Field(gt=0)
    currency: Currency

class ChargeResponse(BaseModel):
    """Response body for the charge endpoint.

    Attributes:
        paid: Whether the payment was approved.
        transaction_id: UUID of the created transaction record.
    """
    paid: bool
    transaction_id: uuid.UUID

@app.get("/health")
def health():
    """Liveness/health probe endpoint.

    Returns:
        dict: A small JSON payload indicating service health.
    """
    return {"ok": True}

@app.post("/charge", response_model=ChargeResponse)
def charge(
    req: ChargeRequest,
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
):
    """Charge a payment with optional idempotency.

    When an ``Idempotency-Key`` header is provided, the endpoint ensures that
    duplicate requests with the same payload are processed at most once. The
    first request will create a transaction and persist the association with
    the key; subsequent retries with the same key and identical payload will
    return the same transaction_id. If the key is reused with a different
    payload, the endpoint responds with HTTP 409.

    Args:
        req: Validated body containing ``amount_cents`` and ``currency``.
        idempotency_key: Optional idempotency key provided via the
            ``Idempotency-Key`` header.

    Returns:
        ChargeResponse: Object containing ``paid`` and ``transaction_id``.

    Raises:
        HTTPException: With status code 409 when the idempotency key is
            reused with a different payload; 500 when creation or lookup
            fails unexpectedly.
    """
    payload_hash = canonical_hash(req.model_dump())

    # Without key: previous behavior (non-idempotent)
    if not idempotency_key:
        tx_id = PaymentsRepo().create_tx(amount_cents=req.amount_cents, currency=req.currency, paid=True)
        if not tx_id:
            raise HTTPException(status_code=500, detail="TX_NOT_CREATED")
        return ChargeResponse(paid=True, transaction_id=tx_id)

    # With key: end-to-end idempotency
    with get_session() as s:  # type: ignore[assignment]
        # Optimistic reservation attempt
        try:
            s.add(IdempotencyKey(key=idempotency_key, request_hash=payload_hash))
            s.commit()
        except IntegrityError:
            s.rollback()
            # Already exists: lock and decide
            rec = s.execute(
                select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key).with_for_update()
            ).scalars().first()
            if not rec:
                raise HTTPException(status_code=500, detail="IDEMPOTENCY_LOOKUP_ERROR")

            if rec.request_hash != payload_hash:
                raise HTTPException(status_code=409, detail="IDEMPOTENCY_CONFLICT")

            # Retry: if a tx is already associated, return the same one
            if rec.transaction_id:
                return ChargeResponse(paid=True, transaction_id=rec.transaction_id)
            # No transaction yet: continue to create it

        # Create transaction and associate it with the key
        tx_id = PaymentsRepo().create_tx(amount_cents=req.amount_cents, currency=req.currency, paid=True)
        if not tx_id:
            raise HTTPException(status_code=500, detail="TX_NOT_CREATED")

        # Associate and persist
        rec = s.get(IdempotencyKey, idempotency_key)
        rec.transaction_id = tx_id
        s.add(rec)
        s.commit()

        return ChargeResponse(paid=True, transaction_id=tx_id)

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = rid
    try:
        response = await call_next(request)
    finally:
        logger.info("request handled", extra={"request_id": rid, "path": request.url.path, "method": request.method})
    response.headers["X-Request-ID"] = rid
    return response