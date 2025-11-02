"""Payments service API built with FastAPI.

This module exposes endpoints to check service health and to charge a
payment. Validation is performed with Pydantic models, while persistence
is delegated to the SQLAlchemy-backed repository in ``repo.PaymentsRepo``.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, constr
from typing import Annotated
import uuid

from repo import PaymentsRepo  # Transaction model with UUID PK + incremental internal_id

app = FastAPI(title="Payments Service")

Currency = constr(pattern=r"^[A-Z]{3}$")

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
def charge(req: ChargeRequest):
    """Charge a payment and persist the transaction.

    For demo purposes, requests that pass validation are approved.
    The created transaction uses a UUID public ID and an internal
    incremental identifier.

    Args:
        req: Charge request containing amount and currency.

    Returns:
        ChargeResponse: Response with approval flag and transaction UUID.

    Raises:
        HTTPException: 500 if the transaction couldn't be created.
    """
    # Demo: if validation passes, approve the payment
    tx_id = PaymentsRepo().create_tx(amount_cents=req.amount_cents, currency=req.currency, paid=True)
    if not tx_id:
        # Fallback if something goes wrong with the database
        raise HTTPException(status_code=500, detail="TX_NOT_CREATED")
    return ChargeResponse(paid=True, transaction_id=tx_id)
