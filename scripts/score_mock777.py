"""Exercise ML scoring -> MySQL Health Score without approving a profile.

Loads a SHADOW_VALIDATION candidate into memory only. The persisted profile and
approval registry remain unchanged; writes are confined to isolated mock schemas.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from sqlalchemy import text

from mock777_env import configure

configure()

from apps.api.app.db import connection  # noqa: E402
from apps.api.app.inference import clean_machine_code, run_inference_and_sync  # noqa: E402


def main() -> None:
    with connection() as conn:
        rows = conn.execute(text("""
            SELECT p.machine_number, p.module, p.profile_version, p.statistics_json,
                   p.threshold_json, p.sv_state, p.state_code
            FROM ht9046mx_calibration_profile p
            JOIN (
                SELECT batch_id FROM ht9046mx_calibration_batch
                ORDER BY completed_at DESC, batch_id DESC LIMIT 1
            ) latest ON latest.batch_id = p.batch_id
            WHERE p.machine_number IN ('777', 'MX777')
              AND p.profile_status = 'SHADOW_VALIDATION'
        """)).mappings().all()
    if len(rows) != 2:
        raise RuntimeError(f"Expected exactly two mock shadow candidates, found {len(rows)}")
    profile_map = {}
    for row in rows:
        stats = json.loads(row["statistics_json"])
        threshold = json.loads(row["threshold_json"])
        profile_map[(clean_machine_code(str(row["machine_number"])), int(row["module"]))] = {
            "profile_id": None,
            "profile_version": f"MOCK_ONLY_{row['profile_version']}",
            "baseline": stats["detailed_baseline"],
            "threshold": float(threshold["deviation_score_q995"]),
            "sv_state": row["sv_state"],
            "state_code": row["state_code"],
        }
    with patch("apps.api.app.inference.get_active_profiles_map", return_value=profile_map):
        result = run_inference_and_sync(target_machines=["MX777"], limit_rows_per_machine=20, sync_to_pm=False)
    with connection() as conn:
        score_rows = conn.execute(text("""
            SELECT module_id, COUNT(*) AS rows_written, MIN(health_score) AS min_score,
                   MAX(health_score) AS max_score
            FROM ht_mock777_source.compressor_health_scores
            WHERE machine_number = 'MX777'
            GROUP BY module_id ORDER BY module_id
        """)).mappings().all()
    print(json.dumps({"mock_only": True, "inference": result, "health_scores": [dict(r) for r in score_rows]}, default=str))


if __name__ == "__main__":
    main()
