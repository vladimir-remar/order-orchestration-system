"""Logging filters for enriching log records with request context.

This module provides a logging filter that injects the current request id
into log records using the ContextVar set by the gateway middleware. Adding
the filter to your logging configuration enables per-request correlation in
logs without modifying individual log statements.
"""

from logging import Filter, LogRecord
from .middleware import REQUEST_ID_CTX


class RequestIdFilter(Filter):
    """Attach a ``request_id`` attribute to log records.

    The value is retrieved from the ``REQUEST_ID_CTX`` ContextVar set by
    ``RequestIdMiddleware``. If no value is present, a hyphen ("-") is used
    as a placeholder so formatters can reliably reference ``%(request_id)s``.
    """

    def filter(self, record: LogRecord) -> bool:
        """Populate ``record.request_id`` and allow the record to be logged.

        Args:
            record: The log record to enrich.

        Returns:
            bool: Always True to indicate the record should be processed.
        """
        try:
            record.request_id = REQUEST_ID_CTX.get()
        except Exception:
            record.request_id = "-"
        return True
