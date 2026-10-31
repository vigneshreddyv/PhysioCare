from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return naive UTC for compatibility with existing Mongo date fields."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
