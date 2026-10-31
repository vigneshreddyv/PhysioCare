from datetime import datetime, timezone

from app.core.time import utc_now


def test_utc_now_preserves_naive_mongo_contract():
    before = datetime.now(timezone.utc).replace(tzinfo=None)

    current = utc_now()

    after = datetime.now(timezone.utc).replace(tzinfo=None)
    assert current.tzinfo is None
    assert before <= current <= after
