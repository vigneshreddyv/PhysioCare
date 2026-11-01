import re
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


def requirement_versions(path: Path) -> dict[str, str]:
    requirements = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^;\s]+)(?:\s*;\s*.+)?",
            line,
        )
        assert match, f"Unpinned requirement in {path.name}: {line}"
        name = match.group(1).casefold().replace("_", "-")
        version = match.group(2)
        assert name not in requirements, f"Duplicate requirement in {path.name}: {name}"
        requirements[name] = version
    return requirements


def test_direct_and_locked_requirements_are_exact_and_python_313_is_in_use():
    direct = requirement_versions(BACKEND / "requirements.txt")
    locked = requirement_versions(BACKEND / "requirements.lock")
    assert direct.items() <= locked.items()
    assert "python-jose" not in locked
    assert "pyjwt" in locked
    assert sys.version_info[:2] == (3, 13)


def test_ci_installs_and_audits_the_locked_graph():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "-r requirements.lock" in workflow
    assert "pip_audit -r requirements.lock" in workflow
    assert "python-version: \"3.13\"" in workflow
