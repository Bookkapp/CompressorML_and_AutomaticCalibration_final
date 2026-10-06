import pytest
from sqlalchemy import create_engine, select

from apps.api.app.qualified_persistence import PersistentRehearsal, batches, runs
from apps.api.app.qualified_stream import CompletedMinuteStream
from apps.api.app.qualified_windows import WindowPolicy
from apps.api.tests.test_qualified_stream import row, clock


@pytest.fixture
def store():
    store = PersistentRehearsal(create_engine("sqlite://"))
    store.create_tables()
    store.initialize("test", CompletedMinuteStream(WindowPolicy("UTC", late_arrival_seconds=30), (6,)), {})
    return store


def test_atomic_rollback_retry_restore_and_long_lived_receipt(store):
    raw = [row(s) for s in range(300)]
    def crash():
        raise RuntimeError("simulated crash")
    with pytest.raises(RuntimeError, match="simulated crash"):
        store.consume("test", "first", raw, as_of=clock(300), next_cursor=300,
                      profiles={}, before_commit=crash)
    assert store.points("test") == []
    with store.engine.connect() as conn:
        assert conn.execute(select(runs.c.source_cursor)).scalar() == 0
        assert conn.execute(select(batches)).first() is None
    assert store.consume("test", "first", raw, as_of=clock(300), next_cursor=300, profiles={})["windows_written"] == 4
    for i in range(35):
        store = PersistentRehearsal(store.engine)
        store.consume("test", f"flush-{i}", [], as_of=clock(330+i*60), next_cursor=300, profiles={})
    assert len(store.points("test")) == 5
    assert all(p["score"]["reason"] == "NO_ACTIVE_PROFILE" for p in store.points("test"))
    assert store.consume("test", "first", raw, as_of=clock(300), next_cursor=300, profiles={})["duplicate_batch"]
    assert len(store.points("test")) == 5


def test_mutated_receipt_cursor_and_contract_are_rejected(store):
    store.consume("test", "a", [row(0)], as_of=clock(60), next_cursor=1, profiles={})
    with pytest.raises(ValueError, match="payload or cursor changed"):
        store.consume("test", "a", [row(1)], as_of=clock(60), next_cursor=1, profiles={})
    with pytest.raises(ValueError, match="cursor did not advance"):
        store.consume("test", "b", [row(1)], as_of=clock(90), next_cursor=1, profiles={})
    with pytest.raises(ValueError, match="contract changed"):
        store.initialize("test", CompletedMinuteStream(WindowPolicy("UTC"), (1,)), {})


def test_dashboard_is_disabled_by_default_and_rejects_remote_target(monkeypatch):
    from fastapi.testclient import TestClient
    from apps.api.app import main
    from apps.api.app.config import Settings
    client = TestClient(main.app)
    for settings in (Settings(_env_file=None), Settings(_env_file=None,
            local_rehearsal_dashboard_enabled=True, analytics_db_host="10.195.17.73")):
        monkeypatch.setattr(main, "get_settings", lambda: settings)
        assert client.get("/api/v1/rehearsal/test/points").status_code == 404


def test_dashboard_returns_persisted_points_and_missing_run(monkeypatch, store):
    from fastapi.testclient import TestClient
    from apps.api.app import main, db
    from apps.api.app.config import Settings
    store.consume("test", "a", [row(s) for s in range(60)], as_of=clock(90), next_cursor=60, profiles={})
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None,
        local_rehearsal_dashboard_enabled=True, analytics_db_host="localhost"))
    # SQLite in-memory connection is thread-bound; use a file for the API thread.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as directory:
        api_store = PersistentRehearsal(create_engine("sqlite:///"+str(Path(directory)/"qa.db")))
        api_store.create_tables()
        api_store.initialize("api-test", CompletedMinuteStream(WindowPolicy("UTC"), (6,)), {})
        api_store.consume("api-test", "a", [row(s) for s in range(60)], as_of=clock(90), next_cursor=60, profiles={})
        monkeypatch.setattr(db, "get_engine", lambda: api_store.engine)
        client = TestClient(main.app)
        response = client.get("/api/v1/rehearsal/api-test/points").json()
        assert response["mode"] == "LOCAL_REHEARSAL_NOT_ACTIVE"
        assert len(response["points"]) == 1
        assert response["points"][0]["score"]["reason"] == "NO_ACTIVE_PROFILE"
        assert client.get("/api/v1/rehearsal/missing/points").status_code == 404
        api_store.engine.dispose()
