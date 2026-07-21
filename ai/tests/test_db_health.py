"""Regression tests for /db/health's error body (app/main.py).

The endpoint is public (Render). psycopg connection failures embed the DSN in
the exception message — host, user, sometimes the password — so the old
`{"detail": str(exc)}` body leaked the Neon connection string to anyone who hit
the endpoint while the DB was down. The client must get a generic body; the
detail belongs in the server log only.

Pure: `ping` is monkeypatched, no DB or network.
"""

import json

import app.main as main_mod


# A realistic psycopg-style failure message: it carries the whole DSN.
_SECRET_DSN = "postgresql://user:s3cr3t-pw@ep-example-123.eu-central-1.aws.neon.tech/db"
_EXC_MESSAGE = f'connection failed: connection to server at "{_SECRET_DSN}" refused'


def test_db_health_error_body_is_generic_and_leaks_nothing(monkeypatch):
    def failing_ping():
        raise RuntimeError(_EXC_MESSAGE)

    monkeypatch.setattr(main_mod, "ping", failing_ping)

    body = main_mod.db_health()

    assert body == {"status": "error", "database": "unreachable"}
    # Belt and braces: no fragment of the exception in the serialized body.
    serialized = json.dumps(body)
    assert "neon.tech" not in serialized
    assert "s3cr3t-pw" not in serialized
    assert "detail" not in body


def test_db_health_error_detail_is_logged_server_side(monkeypatch, caplog):
    def failing_ping():
        raise RuntimeError(_EXC_MESSAGE)

    monkeypatch.setattr(main_mod, "ping", failing_ping)

    with caplog.at_level("ERROR", logger=main_mod.logger.name):
        main_mod.db_health()

    # The operator still sees the real reason (message + traceback).
    assert any("database ping failed" in r.message for r in caplog.records)
    assert _EXC_MESSAGE in caplog.text


def test_db_health_success_shape_is_unchanged(monkeypatch):
    monkeypatch.setattr(main_mod, "ping", lambda: True)
    assert main_mod.db_health() == {"status": "ok", "database": "reachable"}

    monkeypatch.setattr(main_mod, "ping", lambda: False)
    assert main_mod.db_health() == {"status": "error", "database": "reachable"}
