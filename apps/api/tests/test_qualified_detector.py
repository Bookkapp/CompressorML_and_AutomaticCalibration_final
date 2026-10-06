"""Local-only integration tests; fixtures are not real Active Profile approvals."""
from dataclasses import replace
from datetime import timedelta
import json

import pytest
from sqlalchemy import create_engine, select

from apps.api.app.qualified_detector import DurableDetector, seen, issues, outbox, ObservedSourceReader
from apps.api.app.qualified_scoring import ApprovedProfile, QualifiedShadowScorer
from apps.api.app.qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION, WindowPolicy
from apps.api.tests.test_qualified_stream import row, clock, START


def profiles():
    base = dict(hp1=150., lp1=25., hp2=210., lp2=20., dp1=125., dp2=190.,
                valve=90., temphi=80., templo=-10.)
    return {("MX080", 6): ApprovedProfile(1, "fixture-only", WINDOW_VERSION, "MX080", 6,
        "Off", STATE_CODE, base, {f: 1. for f in FEATURES}, 4., "qualified-1m-retained-q995-v1", START)}


def raw(seconds, *, shifted=False):
    return [{**row(s), "source_id": s + 1, **({"Hp_2nd_6": 225.} if shifted else {})} for s in seconds]


@pytest.fixture
def detector():
    value = DurableDetector(create_engine("sqlite://"), WindowPolicy("UTC", late_arrival_seconds=30))
    value.create_tables()
    return value


def test_receipts_restart_overlap_and_atomic_outbox(detector):
    p = profiles()
    run = detector.initialize("MX080", (6,), p)
    data = raw(range(300), shifted=True)
    def crash():
        raise RuntimeError("crash")
    with pytest.raises(RuntimeError, match="crash"):
        detector.cycle(run, data, as_of=clock(300), profiles=p, before_commit=crash)
    assert detector.store.points(run) == []
    with detector.engine.connect() as c:
        assert not c.execute(select(seen)).first()
        assert not c.execute(select(outbox)).first()
    detector.cycle(run, data, as_of=clock(300), profiles=p)
    restored = DurableDetector(detector.engine, detector.policy)
    result = restored.cycle(run, data + raw(range(300, 600), shifted=True), as_of=clock(600), profiles=p)
    assert result["new_source_rows"] == 300
    assert len(restored.store.points(run)) == 9
    assert len(restored.store.episode_summaries(run)) == 1
    restored.cycle(run, [], as_of=clock(630), profiles=p)
    assert len(restored.store.points(run)) == 10
    with detector.engine.connect() as c:
        assert len(c.execute(select(seen)).all()) == 600


def test_low_id_late_commit_is_found_and_finalized_correction_is_reviewed(detector):
    p = profiles()
    run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(59)), as_of=clock(60), profiles=p)
    detector.cycle(run, [{**row(59), "source_id": "low-id"}], as_of=clock(80), profiles=p)
    detector.cycle(run, [], as_of=clock(90), profiles=p)
    assert detector.store.points(run)[0]["window"]["sample_count"] == 60
    amended = {**row(20), "source_id": 21, "Hp_2nd_6": 500.}
    result = detector.cycle(run, [amended, {**row(19), "source_id": "late"}], as_of=clock(120), profiles=p)
    assert result["quarantined_rows"] == 2
    assert len(detector.store.points(run)) == 1
    detector.cycle(run, [amended], as_of=clock(150), profiles=p)
    with detector.engine.connect() as c:
        assert len(c.execute(select(issues)).all()) == 2
        assert len(c.execute(select(outbox).where(outbox.c.kind == "DATA_ISSUE")).all()) == 2


def test_missing_profile_manual_gap_and_profile_replacement(detector):
    p = profiles()
    run = detector.initialize("MX080", (6,), p)
    detector.cycle(run, raw(range(240), shifted=True), as_of=clock(270), profiles=p)
    detector.cycle(run, [{**row(s), "source_id": s+1, "Busy_6": 1} for s in range(240, 300)],
                   as_of=clock(330), profiles=p)
    assert detector.store.episode_summaries(run)[0]["status"] == "UNKNOWN"
    assert detector.store.points(run)[-1]["score"]["status"] == "NOT_SCORED"
    changed = {("MX080", 6): replace(p[("MX080", 6)], profile_id=2)}
    assert detector.initialize("MX080", (6,), changed) != run
    unsupported = detector.initialize("MX057", (1,), {})
    detector.cycle(unsupported, [{**row(s), "source_id": s+1} for s in range(60)], as_of=clock(90), profiles={})
    assert all(x["score"]["primary_score"] is None for x in detector.store.points(unsupported))


def test_duplicate_source_ids_and_policy_changes_fail_closed(detector):
    p = profiles()
    run = detector.initialize("MX080", (6,), p)
    with pytest.raises(ValueError, match="source IDs"):
        detector.cycle(run, raw([0, 0]), as_of=clock(90), profiles=p)
    with pytest.raises(ValueError, match="overlap"):
        DurableDetector(detector.engine, detector.policy, overlap_minutes=1)


def test_prefit_windows_are_not_scored():
    from apps.api.tests.test_qualified_temporal import _window
    p = replace(profiles()[("MX080", 6)], profile_fit_end=START+timedelta(days=1))
    assert QualifiedShadowScorer().score(_window(), p).reason == "BEFORE_PROFILE_FIT_END"


def test_default_entrypoint_has_no_database_writes():
    from apps.api.app.config import Settings
    from apps.api.app.qualified_detector import run_configured_cycle
    assert run_configured_cycle(Settings(_env_file=None))["database_writes"] == 0
