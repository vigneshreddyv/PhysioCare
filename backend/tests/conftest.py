import os
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))


# Ephemeral test-only configuration. No persistent credentials are created.
os.environ.setdefault("JWT_SECRET", "test-access-" + "a" * 40)
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-" + "b" * 40)
os.environ.setdefault("MONGODB_URL", "mongodb://127.0.0.1:1/physiocare_dev")
os.environ.setdefault("DATABASE_NAME", "physiocare_dev")
os.environ.setdefault("PAYMENT_RECONCILIATION_ENABLED", "false")
