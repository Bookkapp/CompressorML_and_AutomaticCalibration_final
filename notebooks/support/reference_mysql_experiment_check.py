"""Repeatable read-only checks of the local SQL experiment (API must be running)."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from sqlalchemy import create_engine, text
from apps.api.app.config import get_settings
from notebooks.support.reference_review_mysql_experiment import SCHEMA


def fetch(path, method="GET"):
    request = Request("http://127.0.0.1:8178" + path, data=b"{}" if method=="POST" else None,
        headers={"Content-Type":"application/json"}, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def main():
    context_status, context = fetch("/api/v1/experiment/source-context")
    day_status, day = fetch("/api/v1/experiment/source-day?machine=MX080&module=6&day=2026-09-07")
    assert context_status == day_status == 200
    assert (context["host"], context["schema"], context["table"]) == ("127.0.0.1", "ht9046mx_iot", "ht9046mx_readings")
    assert sum(p["observations"] for p in day["points"]) == day["rows"] == 1418
    assert day["median_positive_interval_seconds"] == 60 and day["strict_qualified_minutes"] == 0
    assert len(day["points"]) == 1440 and sum(p["hp2"] is None for p in day["points"]) == 22
    assert fetch("/api/v1/experiment/source-day?machine=MX080&module=6&day=2026-10-02")[1]["rows"] == 0
    assert fetch("/api/v1/experiment/source-day?module=9")[0] == 422
    assert fetch("/api/v1/calibration/machines/MX080/approve_all", "POST")[0] == 409
    assert fetch("/api/v1/incidents/simulate_prospective", "POST")[0] == 409
    settings = get_settings()
    engine = create_engine(settings.model_copy(update={"analytics_db_name":SCHEMA}).database_url)
    with engine.connect() as conn:
        counts = {name:conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() for name in
            ("ht9046mx_reference_review_job", "ht9046mx_calibration_profile", "ht9046mx_active_calibration_profile")}
        job = dict(conn.execute(text("SELECT job_id,status,preview_json FROM ht9046mx_reference_review_job ORDER BY created_at DESC LIMIT 1")).mappings().one())
    engine.dispose()
    preview = json.loads(job.pop("preview_json"))
    assert job["status"] == "READY" and preview["summary"]["reference_minutes"] == 0
    assert counts["ht9046mx_active_calibration_profile"] == counts["ht9046mx_calibration_profile"] == 0
    receipt = {"source":context,"selected_day":{k:v for k,v in day.items() if k not in ("points","raw_preview")},
        "job":job,"preview_summary":preview["summary"],"experimental_counts":counts,
        "checks":{"API_raw_count_reconciliation":True,"null_gap_minutes":22,"empty_day":True,
            "invalid_module_rejected":True,"approval_blocked":True,"alerts_blocked":True,"active_and_candidates_zero":True}}
    output = Path(__file__).resolve().parents[1] / "outputs/reference_mysql_experiment_v1/receipt.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"selected_day":receipt["selected_day"],"checks":receipt["checks"],"experimental_counts":counts},default=str))


if __name__ == "__main__":
    main()
