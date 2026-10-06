"""In-memory approval registry fixtures, not changes to real profiles."""
import json
from datetime import datetime
from sqlalchemy import create_engine, text
from apps.api.app.config import Settings
from apps.api.app.qualified_shadow_preview import load_matching_active_profiles
from apps.api.app.qualified_policy import LEGACY_THRESHOLD_VERSION as THRESHOLD_VERSION
from apps.api.app.qualified_windows import FEATURES, STATE_CODE, WINDOW_VERSION


def registry():
    engine = create_engine('sqlite://')
    row = dict(id=1, machine='MX080', module=6, state=STATE_CODE, feature=WINDOW_VERSION,
        stats=json.dumps({'exact_baseline': {f: {'median': 200., 'scale': 2.} for f in FEATURES}}),
        threshold=json.dumps({'method':'qualified_1m_retained_calibration_q995',
            'threshold_version':THRESHOLD_VERSION, 'deviation_score_q995':4.}),
        reasons='[]', validation=json.dumps({'source_pressure_unit':'psig','shadow_elapsed_hours':72,
            'expected_shadow_minutes':4320,'observed_shadow_coverage':1.}), reviewer='fixture-reviewer',
        days=7, n=200, shadow_days=3, shadow_n=200, pct=.5)
    with engine.begin() as c:
        c.execute(text('CREATE TABLE ht9046mx_active_calibration_profile (machine_number TEXT, module INT, sv_state TEXT, state_code TEXT, active_profile_id INT)'))
        c.execute(text('CREATE TABLE ht9046mx_calibration_batch (batch_id INT, feature_version TEXT, source_timezone TEXT)'))
        c.execute(text('''CREATE TABLE ht9046mx_calibration_profile (profile_id INT, batch_id INT,
          profile_version TEXT, statistics_json TEXT, threshold_json TEXT, profile_status TEXT,
          reviewed_at TEXT, reviewer_id TEXT, calibration_end TEXT, calibration_days INT,
          calibration_windows INT, shadow_days INT, shadow_windows INT, shadow_flag_pct REAL,
          reason_codes TEXT, validation_json TEXT)'''))
        c.execute(text("INSERT INTO ht9046mx_active_calibration_profile VALUES (:machine,:module,'Off',:state,:id)"),row)
        c.execute(text("INSERT INTO ht9046mx_calibration_batch VALUES (1,:feature,'UTC')"),row)
        c.execute(text("""INSERT INTO ht9046mx_calibration_profile VALUES (:id,1,'fixture-only',:stats,:threshold,
          'ACTIVE_FROZEN','2026-09-10',:reviewer,'2026-09-07',:days,:n,:shadow_days,:shadow_n,:pct,:reasons,:validation)"""),row)
    return engine


def load(engine):
    return load_matching_active_profiles(Settings(_env_file=None, source_pressure_unit='psig', source_timezone='UTC'),'MX080',engine=engine)


def test_exact_version_and_review_evidence_required():
    engine=registry()
    assert len(load(engine))==1
    for column, value in [('calibration_days',4),('shadow_days',2),('shadow_flag_pct',2),
                          ('reviewer_id','MOCK-FIXTURE'),('reason_codes','["REVIEW_REQUIRED"]'),
                          ('validation_json','{}'),('calibration_days','malformed')]:
        engine=registry()
        with engine.begin() as c:
            c.execute(text(f'UPDATE ht9046mx_calibration_profile SET {column}=:value'),{'value':value})
        assert load(engine)=={}, column


def test_ambiguous_alias_and_legacy_feature_abstain():
    engine=registry()
    with engine.begin() as c:
        c.execute(text("INSERT INTO ht9046mx_active_calibration_profile VALUES ('080',6,'Off',:state,1)"),{'state':STATE_CODE})
    assert load(engine)=={}
    engine=registry()
    with engine.begin() as c:
        c.execute(text("UPDATE ht9046mx_calibration_batch SET feature_version='legacy-minute-snapshot'"))
    assert load(engine)=={}
