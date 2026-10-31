from pathlib import Path
import asyncio

from app.main import health


def test_health_indicator_is_safe_for_home_visit_demo(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "HOME_VISIT_DEMO_MODE", True)
    monkeypatch.setattr(settings, "LAB_DEMO_MODE", False)
    monkeypatch.setattr(settings, "DATABASE_NAME", "physiocare_home_visit_demo")
    monkeypatch.setattr(settings, "RAZORPAY_MODE", "disabled")

    response = asyncio.run(health())

    assert response == {
        "environment": "home_visit_demo",
        "database": "physiocare_home_visit_demo",
        "payments_enabled": False,
    }
    response_text = str(response)
    assert "MONGODB_URL" not in response_text
    assert "JWT_SECRET" not in response_text
    assert "RAZORPAY_KEY_SECRET" not in response_text


def test_home_visit_demo_launcher_is_restricted_to_expected_actions_and_ports():
    script = Path(__file__).parents[1] / "scripts" / "HomeVisitDemo.ps1"
    source = script.read_text(encoding="utf-8")

    assert 'ValidateSet("start", "backend", "frontend", "verify", "stop")' in source
    assert "$MongoPort = 27019" in source
    assert "$BackendPort = 8002" in source
    assert "$FrontendPort = 5176" in source
    assert "required port is already in use" in source
    assert "physiocare-home-visit-demo-mongodb" in source
    assert "Stop-Process -Id" in source
    assert "prepare" not in source
    assert "cleanup" not in source


def test_home_visit_demo_compose_lifecycle_is_project_scoped():
    script = Path(__file__).parents[1] / "scripts" / "HomeVisitDemo.ps1"
    source = script.read_text(encoding="utf-8")

    assert '$ComposeProject = "physiocare-home-visit-demo"' in source
    assert "docker compose -p $ComposeProject -f $ComposeFile up -d mongodb" in source
    assert "docker compose -p $ComposeProject -f $ComposeFile stop mongodb" in source
    assert "docker compose -f (Join-Path $BackendRoot" not in source
    assert "Assert-HomeVisitContainerSafeForStart" in source
    assert "Assert-HomeVisitContainerLabels" in source


def test_home_visit_demo_compose_preserves_existing_volume_and_uses_dedicated_network():
    compose = Path(__file__).parents[1] / "docker-compose.home-visit-demo.yml"
    source = compose.read_text(encoding="utf-8")

    assert "physiocare-home-visit-demo-mongodb-data:/data/db" in source
    assert "physiocare-home-visit-demo-configdb:/data/configdb" in source
    assert "name: backend_physiocare-home-visit-demo-mongodb-data" in source
    assert "name: 320bdd74db72accca6269478ed2d125666d4eb3f88dde3cb7036675732572ea2" in source
    assert source.count("external: true") == 2
    assert "name: physiocare-home-visit-demo-network" in source
    assert '"127.0.0.1:27019:27017"' in source
    assert "physiocare-lab-demo" not in source


def test_lab_demo_compose_is_not_modified_by_home_visit_configuration():
    compose = Path(__file__).parents[1] / "docker-compose.lab-demo.yml"
    source = compose.read_text(encoding="utf-8")

    assert "physiocare-lab-demo-mongodb" in source
    assert "27018" in source
    assert "physiocare-home-visit-demo-network" not in source


def test_home_visit_demo_configuration_keeps_project_and_container_safeguards():
    script = Path(__file__).parents[1] / "scripts" / "HomeVisitDemo.ps1"
    source = script.read_text(encoding="utf-8")

    assert '$ComposeProject = "physiocare-home-visit-demo"' in source
    assert "Assert-HomeVisitContainerSafeForStart" in source
    assert "Assert-HomeVisitContainerLabels" in source
    assert "legacy or foreign container will not be replaced or stopped automatically" in source
