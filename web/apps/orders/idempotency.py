"""Idempotency utilities for safely handling duplicate requests.

This module stores and retrieves idempotency keys to safely de-duplicate
client requests. It supports creating an idempotent record, detecting
conflicts when the same key is used with a different payload, and
finalizing a stored response so subsequent retries can short-circuit.
"""

import hashlib, json
from django.db import transaction, IntegrityError
from .models import IdempotencyKey

def _hash(payload: dict) -> str:
    """Compute a stable SHA-256 hash for a JSON-serializable payload.

    The payload is serialized with sorted keys and compact separators to
    ensure a deterministic representation before hashing.

    Args:
        payload: A JSON-serializable dictionary.

    Returns:
        str: Hex-encoded SHA-256 digest of the normalized payload.
    """
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@transaction.atomic
def get_or_create_idempotent(key: str, payload: dict):
    """Get-or-create an idempotency record for the given key and payload.

    Behavior:
        - First request with a new key: create a record and return (created=False, rec).
        - Subsequent request with same key and same payload: lock and return
          (created=True, rec) for reuse.
        - Subsequent request with same key but different payload: raise
          ValueError("IDEMPOTENCY_CONFLICT").

    The function runs inside a transaction and uses a nested savepoint for the
    create path so IntegrityError only rolls back that block. For the existing
    record path it acquires a row-level lock (SELECT ... FOR UPDATE) to avoid
    races under concurrency.

    Args:
        key: Client-provided idempotency key.
        payload: Request payload used to compute the request hash.

    Returns:
        tuple[bool, IdempotencyKey]: (existing, rec) where existing is True when
        the record already existed, False when it was created in this call.

    Raises:
        ValueError: If the key exists but the payload hash differs
            (idempotency conflict).
    """
    h = _hash(payload)

    try:
        # Nested savepoint: if IntegrityError occurs, only this block is rolled back.
        with transaction.atomic():
            rec = IdempotencyKey.objects.create(
                key=key, request_hash=h, response_status=0, response_body={}
            )
            return False, rec  # created: caller will finalize the response
    except IntegrityError:
        # Already exists: lock and verify hash
        rec = IdempotencyKey.objects.select_for_update().get(key=key)
        if rec.request_hash != h:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return True, rec

def finalize(rec: IdempotencyKey, status_code: int, body: dict, order_id=None):
    """Persist the final response for an idempotent request.

    Stores the HTTP status code and response body, and optionally associates
    the idempotency record with a created order. Subsequent retries can return
    this stored response without re-running side effects.

    Args:
        rec: The idempotency record to update.
        status_code: HTTP status code to store for the response.
        body: JSON-serializable response body to persist.
        order_id: Optional order identifier to link to the idempotency record.
    """
    rec.response_status = status_code
    rec.response_body = body
    if order_id is not None:
        rec.order_id = order_id
    rec.save(update_fields=["response_status", "response_body", "order_id"])