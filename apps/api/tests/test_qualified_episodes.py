from dataclasses import replace
from datetime import timedelta, timezone

import pytest
from sqlalchemy import create_engine, select

from apps.api.app.qualified_episodes import EpisodeArchive, EpisodePolicy
from apps.api.app.qualified_scoring import QualifiedShadowScorer
from apps.api.app.qualified_persistence import PersistentRehearsal, episodes, raw_evidence
from apps.api.app.qualified_stream import CompletedMinuteStream
from apps.api.app.qualified_windows import WindowPolicy
from apps.api.tests.test_qualified_temporal import _window, _profile, START, _raw


def feed(archive, scorer, index, shift=10, **kwargs):
    score = scorer.score(_window(index, hp2_shift=shift), _profile(**kwargs))
    return archive.consume(score, available_at=(START + timedelta(minutes=index+5)).isoformat())


def test_episode_exact_onset_peak_and_five_window_recovery():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    assert feed(archive, scorer, 0, 15) == []
    assert feed(archive, scorer, 1) == []
    episode = feed(archive, scorer, 2)[0]
    assert episode["first_deviation_at"] == START.isoformat()
    assert episode["detected_window_end"] == (START+timedelta(minutes=3)).isoformat()
    assert episode["peak_score"] == 15
    assert episode["top_contributors"][0]["signed_z"] == 15
    assert episode["qualified_windows"] == episode["flagged_windows"] == 3
    for index in range(3, 7):
        assert feed(archive, scorer, index, 0)[0]["status"] == "RECOVERING"
    ended = feed(archive, scorer, 7, 0)[0]
    assert ended["status"] == "RECOVERED"
    assert ended["requested_evidence_end"] == (START+timedelta(minutes=38)).isoformat()


def test_unqualified_and_empty_delivery_never_recover_episode():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    for index in range(3):
        feed(archive, scorer, index)
    bad = replace(_window(3), data_quality_status="LOW_SAMPLE_COVERAGE", features=None)
    result = archive.consume(scorer.score(bad, _profile()), available_at="now")
    assert result[0]["status"] == "UNKNOWN"
    assert result[0]["closed_at"] is None
    assert archive.mark_stale(START+timedelta(minutes=12))[0]["status"] == "UNKNOWN"


def test_profile_change_does_not_merge_or_recover_old_episode():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    for index in range(3):
        feed(archive, scorer, index)
    old = feed(archive, scorer, 3, profile_id=99)[0]
    assert old["status"] == "ENDED_UNKNOWN"
    assert old["close_reason"] == "PROFILE_OR_PARAMETER_CHANGED"
    feed(archive, scorer, 4, profile_id=99)
    new = feed(archive, scorer, 5, profile_id=99)[0]
    assert new["episode_group_id"] != old["episode_group_id"]


def test_short_recurrence_groups_but_preserves_two_segments_and_checkpoint():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    for index in range(3):
        old = feed(archive, scorer, index)
    first_id = old[0]["episode_id"]
    for index in range(3, 8):
        feed(archive, scorer, index, 0)
    archive = EpisodeArchive.from_checkpoint(archive.checkpoint())
    for index in range(8, 11):
        new = feed(archive, scorer, index)
    assert new[0]["episode_id"] != first_id
    assert new[0]["episode_group_id"] == first_id
    assert archive.records[first_id]["closed_at"] is not None


def test_missing_interval_breaks_grouping_and_recovery():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    for index in range(3):
        feed(archive, scorer, index)
    feed(archive, scorer, 3, 0)
    assert feed(archive, scorer, 6, 0)[0]["recovery_run"] == 1


def test_duplicate_and_revision_are_not_new_evidence():
    archive, scorer = EpisodeArchive("test"), QualifiedShadowScorer()
    for index in range(3):
        feed(archive, scorer, index)
    score = scorer.score(_window(2, hp2_shift=10), _profile())
    assert archive.consume(score, available_at="later") == []
    with pytest.raises(ValueError, match="revision"):
        archive.consume(replace(score, primary_score=20), available_at="later")


def test_policy_validation():
    with pytest.raises(ValueError):
        EpisodePolicy(recovery_windows=0)


def test_durable_episode_raw_retry_and_rollback():
    store = PersistentRehearsal(create_engine("sqlite://"))
    store.create_tables()
    profiles = {("MX080", 6): _profile()}
    store.initialize("test", CompletedMinuteStream(WindowPolicy("UTC"), (6,)), profiles)
    rows = [_raw(START+timedelta(seconds=i), hp2=220) for i in range(180)]
    def crash():
        raise RuntimeError("crash")
    with pytest.raises(RuntimeError):
        store.consume("test", "a", rows, as_of=(START+timedelta(minutes=3)).replace(tzinfo=timezone.utc),
            next_cursor=180, profiles=profiles, before_commit=crash)
    with store.engine.connect() as conn:
        assert conn.execute(select(episodes)).first() is None
        assert conn.execute(select(raw_evidence)).first() is None
    clock = (START+timedelta(minutes=3)).replace(tzinfo=timezone.utc)
    store.consume("test", "a", rows, as_of=clock, next_cursor=180, profiles=profiles)
    assert store.consume("test", "a", rows, as_of=clock, next_cursor=180, profiles=profiles)["duplicate_batch"]
    item = store.episode_summaries("test")[0]
    assert item["mode"] == "LOCAL_REHEARSAL_NOT_ACTIVE"
    assert len(store.episode_raw("test", item["episode_id"])["rows"]) == 180
    assert store.episode_raw("test", item["episode_id"], limit=2)["truncated"]
    assert not store.episode_raw("test", item["episode_id"])["coverage_verified"]
    assert len(store.episode_raw("test", item["episode_id"], start=START,
        end=START+timedelta(minutes=1))["rows"]) == 60


def test_second_statistics_preserve_spike_without_changing_primary_feature():
    from apps.api.app.qualified_evidence import minute_evidence
    rows = [_raw(START+timedelta(seconds=i), hp2=210 if i < 59 else 300) for i in range(60)]
    output = minute_evidence(rows, [_window()], lambda x:x)
    stats = output[("MX080",6,START)]["statistics"]["hp2"]
    assert stats["max"] == 300
    assert stats["p95"] == 210
    assert stats["finite_samples"] == 60
    assert _window().features["hp2"] == 210
