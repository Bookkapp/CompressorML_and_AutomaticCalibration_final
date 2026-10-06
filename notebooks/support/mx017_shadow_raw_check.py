"""Bounded read-only source checks supporting the frozen MX017 diagnosis."""
import sys, json, csv
from pathlib import Path
from datetime import datetime
from collections import Counter
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from apps.api.app.config import get_settings
from apps.api.app.reference_raw import read_raw

OUT = ROOT / 'notebooks/outputs/mx017_shadow_diagnosis_20261004'
settings = get_settings()
slices = [
    (1, '2026-09-29T23:30:00', '2026-09-30T00:00:00'),
    (1, '2026-09-30T00:10:00', '2026-09-30T00:20:00'),
    (4, '2026-09-30T01:50:00', '2026-09-30T02:20:00'),
]
checks = []
for module, start, end in slices:
    raw = read_raw(settings, 'MX017', module, datetime.fromisoformat(start), datetime.fromisoformat(end))
    label = f'M{module}_{start[5:10]}_{start[11:16].replace(":", "")}'
    (OUT / f'raw_{label}.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = {k: v for k, v in raw.items() if k != 'chart'}
    summary['state_counts'] = {f: dict(Counter(p[f] for p in raw['chart'])) for f in ('global_state', 'module_state', 'busy', 'sv')}
    summary['features'] = {}
    for feature in ('hp2', 'lp2', 'temphi', 'templo', 'valve', 'dp2'):
        values = [p[feature] for p in raw['chart'] if p[feature] is not None]
        summary['features'][feature] = dict(zip(('min', 'p10', 'median', 'p90', 'max'), map(float, np.quantile(values, [0, .1, .5, .9, 1])))) if values else None
    minute_summary = []
    for minute in sorted(set(p['time'][:16] for p in raw['chart'])):
        points = [p for p in raw['chart'] if p['time'].startswith(minute)]
        row = {'time': minute, 'observed_seconds': len(points), 'sv': dict(Counter(p['sv'] for p in points))}
        for f in ('hp2', 'lp2', 'temphi', 'templo', 'valve'):
            v = [p[f] for p in points if p[f] is not None]
            row[f] = float(np.mean(v)) if v else None
        minute_summary.append(row)
    summary['minute_means'] = minute_summary
    checks.append(summary)
    print(json.dumps({k: summary[k] for k in ('module', 'start', 'end', 'observed_rows', 'expected_seconds', 'state_counts', 'features')}, ensure_ascii=True))
(OUT / 'raw_checks.json').write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding='utf-8')
