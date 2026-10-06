"""Reproducibility and safety checks for the HT9046MX notebook suite."""

from __future__ import annotations

import json
from pathlib import Path

import nbformat
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"
OUTPUT_DIR = NOTEBOOK_DIR / "outputs" / "notebook_qa"
AUTO_DIR = NOTEBOOK_DIR / "outputs" / "ht9046mx_autobootstrap"
MX080_DIR = NOTEBOOK_DIR / "outputs" / "mx080_module6_forensics_v2_hp180"
SHADOW_DIR = NOTEBOOK_DIR / "outputs" / "ht9046mx_phase7_shadow_replay_v2_hp180"


def record(checks: list[dict], name: str, passed: bool, evidence: object) -> None:
    checks.append({"check": name, "passed": bool(passed), "evidence": evidence})


checks: list[dict] = []
notebook_inventory: list[dict] = []

for path in sorted(NOTEBOOK_DIR.glob("*.ipynb")):
    notebook = nbformat.read(path, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code" and cell.source.strip()]
    errors = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    unrun = [cell for cell in code_cells if cell.get("execution_count") is None]
    notebook_inventory.append(
        {
            "notebook": path.name,
            "cells": len(notebook.cells),
            "code_cells": len(code_cells),
            "unrun_code_cells": len(unrun),
            "saved_error_outputs": len(errors),
        }
    )

record(checks, "all notebooks executed", all(row["unrun_code_cells"] == 0 for row in notebook_inventory), notebook_inventory)
record(checks, "no saved notebook errors", all(row["saved_error_outputs"] == 0 for row in notebook_inventory), notebook_inventory)

required_sections = {
    "00_HT9046MX_Notebook_Navigator_Colab.ipynb": ["## tl;dr", "## Context & Methods", "## Data", "## Results", "## Takeaways"],
    "06_HT9046MX_AutoBootstrap_Profile_Lifecycle_Colab.ipynb": ["## tl;dr", "## Context & Methods", "## Data", "## Results", "## Takeaways"],
    "07D_MX080_Module6_OneSecond_Forensics_Colab.ipynb": ["## tl;dr", "## Context & Methods", "## Data", "## Results", "## Takeaways"],
    "07_HT9046MX_Server_Shadow_Replay_Colab.ipynb": ["## tl;dr", "## Context & Methods", "## Data", "## Results", "## Takeaways"],
}
for filename, headings in required_sections.items():
    notebook = nbformat.read(NOTEBOOK_DIR / filename, as_version=4)
    markdown = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "markdown")
    missing = [heading for heading in headings if heading not in markdown]
    record(checks, f"presentation sections: {filename}", not missing, {"missing": missing})

summary = json.loads((AUTO_DIR / "analysis_summary.json").read_text(encoding="utf-8"))
manifest = json.loads((AUTO_DIR / "run_manifest.json").read_text(encoding="utf-8"))
lifecycle = pd.read_csv(AUTO_DIR / "profile_lifecycle_status.csv")
events = pd.read_csv(AUTO_DIR / "event_profile_readiness.csv")
approval = pd.read_csv(AUTO_DIR / "approval_package.csv")
candidate_files = sorted((AUTO_DIR / "candidate_profiles").glob("machine_*_candidate.json"))

record(checks, "source period and timezone disclosed", summary["source_period"] == {"start": "2026-08-04 00:00:00", "end": "2026-09-01 17:10:00", "timezone": "not encoded"}, summary["source_period"])
record(checks, "verified minute counts retained", summary["minute_rows"] == 3_548_928 and summary["eligible_rows"] == 2_667_008, {"minute_rows": summary["minute_rows"], "eligible_rows": summary["eligible_rows"]})
record(checks, "profile count reconciles", len(lifecycle) == len(approval) == summary["steady_profiles"] == 262, {"lifecycle": len(lifecycle), "approval": len(approval), "summary": summary["steady_profiles"]})
record(checks, "lifecycle counts reconcile", lifecycle["lifecycle_status"].value_counts().to_dict() == summary["steady_status_counts"], lifecycle["lifecycle_status"].value_counts().to_dict())
record(checks, "no automatic activation", not lifecycle["auto_activation_allowed"].astype(bool).any() and not lifecycle["lifecycle_status"].isin(["READY_FOR_APPROVAL", "ACTIVE_FROZEN"]).any() and not summary["auto_activation_allowed"], {"highest_state": summary["highest_possible_state_this_run"]})
record(checks, "event strata remain coverage-limited", len(events) == summary["event_strata"] == 524 and set(events["event_status"]) == {"INSUFFICIENT_COVERAGE"}, events["event_status"].value_counts().to_dict())
record(checks, "candidate package exists for every machine", len(candidate_files) == 19, {"candidate_json_files": len(candidate_files)})
record(checks, "temporal split declared", "past calibration then future shadow" in manifest["split_contract"], manifest["split_contract"])
record(checks, "threshold fitted from calibration only", "retained calibration only" in manifest["threshold_contract"], manifest["threshold_contract"])
record(checks, "service epoch remains unverified", lifecycle["service_epoch"].eq("epoch-unverified-20260804-20260901").all(), {"service_epoch": lifecycle["service_epoch"].unique().tolist()})
record(
    checks,
    "Phase 6 hp180 candidate versions are explicit",
    manifest["profile_version"] == "autobootstrap-candidate-v2-hp180"
    and manifest["feature_version"] == "minute-state-core-hp180-v2"
    and lifecycle["profile_version"].eq("autobootstrap-candidate-v2-hp180").all()
    and lifecycle["feature_version"].eq("minute-state-core-hp180-v2").all()
    and "hp2_below_180_pct" in lifecycle.columns
    and "hp2_below_200_pct" not in lifecycle.columns,
    {
        "profile_version": manifest["profile_version"],
        "feature_version": manifest["feature_version"],
        "hp2_screening_column": "hp2_below_180_pct",
    },
)

mx080_summary = json.loads((MX080_DIR / "analysis_summary.json").read_text(encoding="utf-8"))
mx080_figures = [Path(path) for path in mx080_summary["figures"].values()]
record(
    checks,
    "MX-080 Module 6 forensic scope and counts",
    mx080_summary["module"] == 6
    and mx080_summary["module6_alm043_sep7_count"] == 7
    and mx080_summary["module6_alm041_sep8_count"] == 2
    and "duplicate timestamps excluded" in mx080_summary["row_grain"],
    {
        "machine": mx080_summary["machine"],
        "module": mx080_summary["module"],
        "ALM043": mx080_summary["module6_alm043_sep7_count"],
        "ALM041_followup": mx080_summary["module6_alm041_sep8_count"],
        "row_grain": mx080_summary["row_grain"],
    },
)
record(
    checks,
    "MX-080 Module 6 figures exist",
    len(mx080_figures) == 4 and all(path.exists() and path.stat().st_size > 0 for path in mx080_figures),
    {path.name: path.stat().st_size if path.exists() else 0 for path in mx080_figures},
)
record(
    checks,
    "MX-080 hp180 rule and water-log evidence are explicit",
    mx080_summary["hp2_qualified_field_reference_band_psi"] == [180.0, 230.0]
    and mx080_summary["undercharge_screening_boundary_psi"] == 180.0
    and mx080_summary["water_keyword_messages_all_available_logs"] == 1
    and mx080_summary["water_keyword_messages_sep3_to_sep8"] == 0,
    {
        "band": mx080_summary["hp2_qualified_field_reference_band_psi"],
        "water_hits_all_logs": mx080_summary["water_keyword_messages_all_available_logs"],
        "water_hits_sep3_to_sep8": mx080_summary["water_keyword_messages_sep3_to_sep8"],
    },
)

shadow_summary = json.loads((SHADOW_DIR / "replay_summary.json").read_text(encoding="utf-8"))
shadow_manifest = json.loads((SHADOW_DIR / "shadow_release_manifest.json").read_text(encoding="utf-8"))
failure_tests = pd.read_csv(SHADOW_DIR / "failure_mode_tests.csv")
record(
    checks,
    "Phase 7 model selected without outer/incident tuning",
    shadow_summary["selected_model"] == "ARX-Ridge__seed_13"
    and shadow_summary["selection_rule"] == "locked from inner validation before outer and MX-080 replay"
    and shadow_manifest["model_selection_source"] == "inner temporal validation only",
    {"model": shadow_summary["selected_model"], "selection": shadow_summary["selection_rule"]},
)
record(
    checks,
    "Phase 7 hp180 versions are locked consistently",
    shadow_manifest["replay_version"] == "phase07-shadow-replay-v2-hp180"
    and shadow_manifest["registry_version"] == "phase07-shadow-registry-v2-hp180"
    and shadow_manifest["feature_version"] == "minute-relative-regime-hp180-v3"
    and shadow_manifest["threshold_version"] == "past-calibration-q995-hp180-v2"
    and shadow_manifest["hp2_reference_policy"]["qualified_reference_band_psi"] == [180.0, 230.0]
    and shadow_summary["historical_release_comparison"]["persistent_alert_delta"] == -1,
    {
        "replay": shadow_manifest["replay_version"],
        "registry": shadow_manifest["registry_version"],
        "feature": shadow_manifest["feature_version"],
        "threshold": shadow_manifest["threshold_version"],
        "reference_band": shadow_manifest["hp2_reference_policy"]["qualified_reference_band_psi"],
        "persistent_alert_delta": shadow_summary["historical_release_comparison"]["persistent_alert_delta"],
    },
)
record(
    checks,
    "Phase 7 replay failure modes fail closed",
    len(failure_tests) == 12 and failure_tests["expected_behavior_met"].astype(bool).all(),
    failure_tests[["test", "result_status", "expected_behavior_met"]].to_dict(orient="records"),
)
record(
    checks,
    "Phase 7 restart is deterministic",
    shadow_summary["primary"]["restart_deterministic"] is True,
    shadow_summary["primary"],
)
record(
    checks,
    "MX-080 replay keeps profile and timing caveats",
    shadow_summary["mx080"]["reference_days"] == 4
    and shadow_summary["mx080"]["profile_status"] == "INCIDENT_REPLAY_ONLY_INSUFFICIENT_FOR_PRODUCTION"
    and shadow_summary["mx080"]["pre_transition_raw_flag_rate_pct"] < shadow_summary["mx080"]["post_transition_raw_flag_rate_pct"]
    and "not validated fault lead time" in shadow_summary["mx080"]["timing_interpretation"],
    shadow_summary["mx080"],
)
record(
    checks,
    "Phase 7 activation and rollback remain blocked",
    shadow_manifest["auto_activation_allowed"] is False
    and shadow_manifest["activation_state"] == "SHADOW_ONLY_NOT_AUTHORIZED"
    and shadow_manifest["rollback_target"] is None,
    {"activation": shadow_manifest["activation_state"], "rollback": shadow_manifest["rollback_status"]},
)
record(
    checks,
    "Server handoff and MySQL shadow schema exist",
    (ROOT / "deployment" / "README_Server_Shadow.md").exists()
    and (ROOT / "deployment" / "mysql_shadow_schema.sql").exists(),
    {"deployment_dir": str(ROOT / "deployment")},
)

result = {
    "qa_date": "2026-09-10",
    "status": "PASS_WITH_CAVEATS" if all(item["passed"] for item in checks) else "FAIL",
    "checks_passed": sum(item["passed"] for item in checks),
    "checks_total": len(checks),
    "checks": checks,
    "limitations": [
        "No technician-confirmed fault labels; results are readiness and shadow-screening evidence, not diagnostic accuracy.",
        "Service/refill epochs and source timezone are not encoded.",
        "Busy/Status interpretation still awaits the controller codebook.",
        "Recipe, load and facility-water context are not available.",
    ],
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "notebook_qa_summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
pd.DataFrame(notebook_inventory).to_csv(OUTPUT_DIR / "notebook_execution_inventory.csv", index=False)

print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"]}, ensure_ascii=False))
if result["status"] == "FAIL":
    failed = [item["check"] for item in checks if not item["passed"]]
    raise SystemExit(f"QA failed: {failed}")
