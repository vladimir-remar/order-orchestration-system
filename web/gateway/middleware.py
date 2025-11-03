"""Middleware that assigns and propagates a request identifier.

This module provides a small Django middleware that ensures every incoming
HTTP request receives a request identifier (UUID). The identifier is read
from the incoming ``X-Request-Id`` header when provided by the client, or
generated server-side otherwise. The middleware stores the id on the
``request`` object and in a context variable so code running downstream can
access it without passing the value explicitly.

Behavior contract:
- If the incoming request contains the ``X-Request-Id`` header, that value
  is reused as the request id.
- Otherwise a new UUIDv4 is generated.
- The response will include the same id in the ``X-Request-ID`` header.

This middleware is intentionally small and synchronous to remain compatible
with Django's middleware API used in this project.
"""

import uuid
import os
import contextvars
from django.http import JsonResponse

from django.utils.deprecation import MiddlewareMixin

REQUEST_ID_CTX = contextvars.ContextVar("request_id", default="-")
MAX_API_BYTES = int(os.getenv("API_MAX_BYTES", str(1 * 1024 * 1024)))

class RequestIdMiddleware(MiddlewareMixin):
    """Django middleware that sets and returns a per-request identifier.

    Attributes:
        HEADER (str): The name of the incoming HTTP header (in Django's
            ``request.META`` casing) that may contain a client-provided id.
        RESPONSE_HEADER (str): The name of the header returned on responses.
    """

    HEADER = "HTTP_X_REQUEST_ID"       # incoming header as found in request.META
    RESPONSE_HEADER = "X-Request-ID"   # header to add to outgoing responses

    def process_request(self, request):
        """Populate the request with a request id and set a context var.

        If the client supplied an id in the configured header it is reused.
        Otherwise a new UUIDv4 string is generated.

        The id is stored on ``request.request_id`` for easy access in views
        and also stored in a ContextVar named ``REQUEST_ID_CTX`` for code
        that runs outside the request object (for example library code or
        log record processors).

        Args:
            request: Django HttpRequest instance.
        """
        rid = request.META.get(self.HEADER)
        if not rid:
            rid = str(uuid.uuid4())
        request.request_id = rid
        REQUEST_ID_CTX.set(rid)

    def process_response(self, request, response):
        """Ensure the response contains the request id header and return it.

        The method prefers the id attached to the request object but falls
        back to the ContextVar value when the request object is not present
        (for example in some error handlers).

        Args:
            request: Django HttpRequest (may be None in rare cases).
            response: Django HttpResponse to modify.

        Returns:
            The same HttpResponse instance with the ``X-Request-ID`` header set.
        """
        rid = getattr(request, "request_id", REQUEST_ID_CTX.get())
        response[self.RESPONSE_HEADER] = rid
        return response

class ApiSizeLimitMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith("/api/"):
            clen = request.META.get("CONTENT_LENGTH")
            if clen and clen.isdigit() and int(clen) > MAX_API_BYTES:
                return JsonResponse({"detail": "PAYLOAD_TOO_LARGE"}, status=413)