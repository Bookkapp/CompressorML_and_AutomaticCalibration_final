"""Frozen, explicit model coverage. Excluded states retain data and events.

Legacy reviewed profiles without this policy keep their original semantics.
Changing a policy creates a new reviewed profile and invalidates validation.
"""
from collections import Counter
from .unified_events import fingerprint

VERSION = "explicit-sv-evaluation-scope-v1"
STATES = ("OFF", "ON")


def state_of(context):
    return next((s for s in STATES if context and context.endswith("_SV_"+s)), None)


def make_scope(included, reason):
    if not included or len(included) != len(set(included)) or not set(included) <= set(STATES):
        raise ValueError("Choose at least one unique supported SV state")
    excluded = sorted(set(STATES)-set(included))
    if excluded and len(reason.strip()) < 8:
        raise ValueError("Explain excluded SV states in at least 8 characters")
    return {"version": VERSION, "included_sv_states": sorted(included),
            "excluded_sv_states": excluded, "excluded_reason": reason.strip(),
            "unknown_behavior": "NOT_EVALUATED", "data_and_events_retained": True}


def scope_of(model):
    scope = (model.get("reference_review") or {}).get("evaluation_scope")
    if scope is None:
        return None
    if scope.get("version") != VERSION or scope != make_scope(scope.get("included_sv_states"), scope.get("excluded_reason", "")):
        raise ValueError("Invalid frozen evaluation scope")
    return scope


def scope_hash(model):
    return fingerprint(scope_of(model))


def validation_receipt(points, model):
    assessed = [p for p in points if p["category"] in {
        "WITHIN_PROPOSED_STEADY", "WITHIN_PROPOSED_TRANSITION", "UNEXPECTED_TRANSITION", "STEADY_DEVIATION"}]
    days = Counter(p["time"][:10] for p in assessed)
    flagged = sum(p["category"] in {"UNEXPECTED_TRANSITION", "STEADY_DEVIATION"} for p in assessed)
    counts = Counter(p["category"] for p in points)
    mock = sum("mock_normal" in p.get("state_counts", {}).get("compressor", {}) for p in points)
    provenance = {"source_kind":"MOCK", "approval_eligible":False, "mock_minutes":mock} if mock else {}
    return {**provenance, "supported_days": sum(n >= 60 for n in days.values()), "supported_minutes": len(assessed),
            "flag_pct": 100*flagged/len(assessed) if assessed else 100.,
            "unresolved_minutes": sum(counts[k] for k in ("NEW_STEADY_LEVEL", "UNSUPPORTED_TRANSITION", "INSUFFICIENT_REFERENCE")),
            "excluded_state_minutes": counts["STATE_GATE_EXCLUDED"], "observed_minutes": len(points),
            "data_unavailable_minutes": counts["DATA_UNAVAILABLE"], "categories": dict(counts),
            "evaluation_scope_fingerprint": scope_hash(model)}


def coverage_rows(model):
    scope = scope_of(model)
    review = model.get("reference_review") or {}
    accepted = set(review.get("accepted_regime_ids", []))
    rows = []
    for state in STATES:
        regimes = [r for r in model["regimes"] if state_of(r["context"]) == state]
        supported = [r for r in regimes if r["coverage_supported"]]
        chosen = [r for r in supported if r["regime_id"] in accepted]
        observed = model.get("context_coverage", {}).get(state, {})
        included = scope is None or state in scope["included_sv_states"]
        rows.append({"sv": state, "included": included, "reference_minutes": observed.get("minutes"),
                     "reference_days": observed.get("days"), "proposed_steady_minutes": sum(r["minutes"] for r in regimes),
                     "best_regime_days": max((r["days"] for r in regimes), default=0),
                     "supported_regimes": len(supported), "accepted_regimes": len(chosen),
                     "status": "STATE_GATE_EXCLUDED" if not included else "REFERENCE_REVIEWED" if chosen else
                         "NEEDS_REVIEW" if supported else "INSUFFICIENT_REFERENCE",
                     "reason": scope["excluded_reason"] if not included else ""})
    return rows
