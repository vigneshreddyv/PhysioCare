"""The connected contract must refuse ambiguous or unapproved Mongo targets."""

import pytest

import test_report_transaction_connected_mongo as contract


def configure(monkeypatch, *, mode, url, database, ack, host="", replica_set=""):
    values = {
        "TEST_MODE": mode,
        "TEST_URL": url,
        "TEST_DATABASE": database,
        "TEST_ACK": ack,
        "APPROVED_HOST": host,
        "APPROVED_REPLICA_SET": replica_set,
    }
    for name, value in values.items():
        monkeypatch.setattr(contract, name, value)


def test_exact_loopback_identity_can_enable_contract(monkeypatch):
    configure(
        monkeypatch,
        mode="loopback",
        url="mongodb://127.0.0.1:27017/physiocare_phase15_txn_contract?replicaSet=rs0",
        database="physiocare_phase15_txn_contract",
        ack="empty-loopback-replica-set-only",
    )
    assert contract.explicitly_enabled()


@pytest.mark.parametrize(
    "url",
    [
        "mongodb://127.0.0.1:27017/physiocare",
        "mongodb://127.0.0.1:27017,another.invalid:27017/physiocare_phase15_txn_contract",
        "mongodb://production.invalid:27017/physiocare_phase15_txn_contract",
        "mongodb://127.0.0.1/physiocare_phase15_txn_contract",
    ],
)
def test_loopback_rejects_ambiguous_or_wrong_target(monkeypatch, url):
    configure(
        monkeypatch,
        mode="loopback",
        url=url,
        database="physiocare_phase15_txn_contract",
        ack="empty-loopback-replica-set-only",
    )
    assert not contract.explicitly_enabled()


def test_exact_staging_identity_can_enable_contract(monkeypatch):
    configure(
        monkeypatch,
        mode="staging",
        url="mongodb://staging.mongo.example.invalid:27017/physiocare_staging?tls=true",
        database="physiocare_staging",
        ack="approved-empty-isolated-staging-only",
        host="staging.mongo.example.invalid",
        replica_set="approved-rs",
    )
    assert contract.explicitly_enabled()


@pytest.mark.parametrize(
    ("host", "replica_set", "database"),
    [
        ("other.mongo.example.invalid", "approved-rs", "physiocare_staging"),
        ("staging.mongo.example.invalid", "", "physiocare_staging"),
        ("staging.mongo.example.invalid", "approved-rs", "physiocare"),
    ],
)
def test_staging_rejects_incomplete_or_mismatched_approval(
    monkeypatch, host, replica_set, database
):
    configure(
        monkeypatch,
        mode="staging",
        url="mongodb://staging.mongo.example.invalid:27017/physiocare_staging?tls=true",
        database=database,
        ack="approved-empty-isolated-staging-only",
        host=host,
        replica_set=replica_set,
    )
    assert not contract.explicitly_enabled()


@pytest.mark.parametrize(
    "query",
    ["", "?tls=false", "?tls=true&tlsInsecure=true", "?tls=true&tlsAllowInvalidCertificates=true"],
)
def test_staging_rejects_missing_or_unverified_tls(monkeypatch, query):
    configure(
        monkeypatch,
        mode="staging",
        url=f"mongodb://staging.mongo.example.invalid:27017/physiocare_staging{query}",
        database="physiocare_staging",
        ack="approved-empty-isolated-staging-only",
        host="staging.mongo.example.invalid",
        replica_set="approved-rs",
    )
    assert not contract.explicitly_enabled()
