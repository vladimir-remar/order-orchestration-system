"""Pydantic schemas for orders.

This module exposes lightweight request/validation schemas used by the
orders API and service layer.
"""

import re
from pydantic import BaseModel, Field, field_validator


SKU_RE = re.compile(r"^[A-Z0-9_-]{3,32}$")
CURRENCIES = {"EUR", "USD", "GBP"}


class OrderItemIn(BaseModel):
    """Input schema for a single order line item.

    Attributes:
        sku: Product SKU. Will be normalized to uppercase and validated
            against a regex (3-32 chars, uppercase letters, digits, '_' and '-').
        quantity: Positive integer indicating units requested.
    """

    sku: str = Field(min_length=3, max_length=32)
    quantity: int = Field(gt=0)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        """Validate and normalize SKU to uppercase.

        Args:
            v: Raw SKU value from the incoming payload.

        Returns:
            Uppercased SKU string if valid.

        Raises:
            ValueError: When the SKU does not match the expected pattern.
        """
        v2 = v.upper()
        if not SKU_RE.match(v2):
            raise ValueError("Invalid SKU format")
        return v2


class CreateOrderDTO(BaseModel):
    """Schema for creating an order.

    Attributes:
        items: List of `OrderItemIn` items.
        amount_cents: Total amount in integer cents (must be > 0).
        currency: 3-letter ISO currency code. Normalized to uppercase and
            validated against a small supported set.
    """

    items: list[OrderItemIn]
    amount_cents: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate and normalize currency code.

        Args:
            v: Raw currency code from the incoming payload.

        Returns:
            Uppercased currency code if supported.

        Raises:
            ValueError: When the currency is not in the supported set.
        """
        v2 = v.upper()
        if v2 not in CURRENCIES:
            raise ValueError("Unsupported currency")
        return v2
