from pathlib import Path


def test_home_visit_fixture_script_isolated_and_non_destructive():
    script = Path(__file__).parents[1] / "scripts" / "HomeVisitDemoFixtures.py"
    source = script.read_text(encoding="utf-8")

    assert 'choices=("prepare",)' in source
    assert "PHYSIOCARE_HOME_VISIT_ENV_FILE" in source
    assert "BACKEND_ROOT" in source
    assert "HOME_VISIT_DEMO_DATABASE_NAME" in source
    assert "HOME_VISIT_DEMO_MONGODB_URL" in source
    assert "PhysioCareHomeVisitDemo" in source
    assert "credentials.json" in source
    assert "appointments" not in source
    assert ".delete()" not in source
    assert "drop_database" not in source


def test_home_visit_fixture_contains_required_identities_and_prerequisites():
    script = Path(__file__).parents[1] / "scripts" / "HomeVisitDemoFixtures.py"
    source = script.read_text(encoding="utf-8")

    assert "homevisit.patient@physiocare-demo.internal" in source
    assert "homevisit.doctor@physiocare-demo.internal" in source
    assert "homevisit.admin@physiocare-demo.internal" in source
    assert 'role": "patient"' in source
    assert 'role": "doctor"' in source
    assert 'role": "admin"' in source
    assert "accepts_home_visits = True" in source
    assert "PATIENT_ADDRESS" in source
    assert 'service_mode="home_visit"' in source
    assert 'start_time="09:00"' in source
    assert 'end_time="10:00"' in source
    assert "published_revision" in source
