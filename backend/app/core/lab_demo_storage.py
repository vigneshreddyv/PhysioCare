import csv
import io
import os
import re
import subprocess
from pathlib import Path

from app.core.config import lab_demo_home, settings


_REPORT_KEY_PATTERN = re.compile(r"^[0-9a-f]{32}\.pdf$")
SAMPLE_REPORT_NAME = "lab-demo-sample.pdf"


def report_storage_root() -> Path:
    settings.validate_lab_demo_isolation()
    configured = Path(settings.LAB_REPORT_STORAGE_DIR).expanduser()
    if settings.LAB_DEMO_MODE and not configured.is_absolute():
        raise RuntimeError("Laboratory demo report storage must be an absolute directory")
    if configured.is_symlink():
        raise RuntimeError("Laboratory report storage cannot be a symbolic link")
    root = configured.resolve()
    return root


def report_file_path(storage_key: str) -> Path:
    if (
        not isinstance(storage_key, str)
        or not storage_key
        or storage_key in {".", ".."}
        or "/" in storage_key
        or "\\" in storage_key
        or Path(storage_key).name != storage_key
    ):
        raise ValueError("Invalid laboratory report storage key")
    root = report_storage_root()
    candidate = root / storage_key
    if candidate.is_symlink() or candidate.resolve().parent != root:
        raise ValueError("Laboratory report path is outside private storage")
    return candidate


def is_generated_report_key(storage_key: str) -> bool:
    return bool(_REPORT_KEY_PATTERN.fullmatch(storage_key))


def secure_report_storage() -> Path:
    root = report_storage_root()
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink():
        raise RuntimeError("Laboratory report storage cannot be a symbolic link")
    if os.name == "nt":
        _restrict_windows_acl(root, directory=True)
    else:
        os.chmod(root, 0o700)
    return root


def secure_demo_home() -> Path:
    home = lab_demo_home()
    if home.is_symlink():
        raise RuntimeError("Laboratory demo data directory cannot be a symbolic link")
    home.mkdir(mode=0o700, parents=True, exist_ok=True)
    if home.is_symlink():
        raise RuntimeError("Laboratory demo data directory cannot be a symbolic link")
    if os.name == "nt":
        _restrict_windows_acl(home, directory=True)
    else:
        os.chmod(home, 0o700)
    return home


def secure_private_file(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("Private laboratory demo files cannot be symbolic links")
    if os.name == "nt":
        _restrict_windows_acl(path, directory=False)
    else:
        os.chmod(path, 0o600)


def _restrict_windows_acl(path: Path, *, directory: bool) -> None:
    identity = subprocess.run(
        ["whoami.exe", "/user", "/fo", "csv", "/nh"],
        check=True,
        capture_output=True,
        text=True,
    )
    rows = list(csv.reader(io.StringIO(identity.stdout)))
    sid = next(
        (row[-1].strip() for row in rows if row and row[-1].strip().startswith("S-")),
        None,
    )
    if not sid or not re.fullmatch(r"S-\d-(?:\d+-)*\d+", sid):
        raise RuntimeError("Could not verify the current Windows user for private file permissions")

    rights = "(OI)(CI)F" if directory else "F"
    subprocess.run(
        ["icacls.exe", str(path), "/inheritance:r", "/grant:r", f"*{sid}:{rights}"],
        check=True,
        capture_output=True,
        text=True,
    )
