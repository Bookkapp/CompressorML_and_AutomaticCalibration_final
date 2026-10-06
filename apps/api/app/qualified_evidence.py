"""Observed-second summaries for review only; never primary score inputs."""
from collections import defaultdict
import math

import numpy as np

from .qualified_windows import SOURCE_FIELDS


def minute_evidence(rows, windows, localize):
    grouped = defaultdict(list)
    for row in rows:
        stamp = localize(row["recorded_at"]).replace(second=0, microsecond=0)
        grouped[(str(row["machine_number"]), stamp)].append(row)
    output = {}
    for window in windows:
        observed = grouped[(window.machine_number, window.window_start)]
        statistics = {}
        for feature, template in SOURCE_FIELDS.items():
            values = []
            for row in observed:
                value = row.get(template.format(module=window.module))
                if value is None or isinstance(value, bool):
                    continue
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.append(value)
            statistics[feature] = {"finite_samples": len(values),
                "min": min(values) if values else None, "max": max(values) if values else None,
                "p05": float(np.quantile(values, .05)) if values else None,
                "p95": float(np.quantile(values, .95)) if values else None,
                "iqr": float(np.quantile(values, .75)-np.quantile(values, .25)) if values else None}
        output[(window.machine_number, window.module, window.window_start)] = {
            "mode": "REVIEW_EVIDENCE_NOT_SCORE_INPUT", "observed_rows": len(observed),
            "qualified": window.eligible, "statistics": statistics}
    return output
