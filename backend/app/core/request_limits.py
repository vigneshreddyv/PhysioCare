"""Application-level limits for untrusted request bodies."""

import logging

from fastapi import HTTPException, Request, status


logger = logging.getLogger(__name__)

# Non-upload mutation bodies in this application are small structured records.
# One MiB is a defensive transport ceiling, not a clinical per-field policy.
MAX_JSON_REQUEST_BYTES = 1024 * 1024

# The supported webhook extracts only the event name and payment/order IDs.
# Keep a separate, smaller fail-safe until the provider contract is verified
# against an approved staging capture.
MAX_RAZORPAY_WEBHOOK_BYTES = 256 * 1024
MAX_RAZORPAY_SIGNATURE_CHARS = 256
MAX_RAZORPAY_EVENT_ID_CHARS = 128
MAX_RAZORPAY_ENTITY_ID_CHARS = 128


def _declared_content_length(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        length = int(value)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Content-Length header",
        ) from None
    if length < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Content-Length header",
        )
    return length


def _too_large(request: Request, observed: int, maximum: int) -> HTTPException:
    logger.warning(
        "Request body rejected: route=%s category=body_too_large "
        "observed_bytes=%s max_bytes=%s",
        request.url.path,
        observed,
        maximum,
    )
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail="Request body is too large",
    )


async def read_bounded_body(request: Request, maximum: int) -> bytes:
    """Read one ASGI body stream without retaining bytes beyond ``maximum``."""
    declared = _declared_content_length(request)
    if declared is not None and declared > maximum:
        raise _too_large(request, declared, maximum)

    body = bytearray()
    async for chunk in request.stream():
        next_size = len(body) + len(chunk)
        if next_size > maximum:
            raise _too_large(request, next_size, maximum)
        body.extend(chunk)
    return bytes(body)

