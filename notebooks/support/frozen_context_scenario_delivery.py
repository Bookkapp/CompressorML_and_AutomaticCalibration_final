"""Build/execute the saved-evidence scenario notebook; no live data writes."""
from pathlib import Path
import gzip
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import nbformat
from nbclient import NotebookClient

from notebooks.support.frozen_context_scenarios import OUT, PHYSICAL

ROOT = Path(__file__).resolve().parents[2]
BOOK = ROOT / 'notebooks/15_Frozen_Context_Scenarios_20261006.ipynb'
COLORS = {'WITHIN_PROPOSED_STEADY': '#28759a', 'STEADY_DEVIATION': '#a94838',
    'NEW_STEADY_LEVEL': '#cb9539', 'UNSUPPORTED_TRANSITION': '#765f9e',
    'STATE_GATE_EXCLUDED': '#879097', 'DATA_UNAVAILABLE': '#aab3bb',
    'UNSUPPORTED_CONTROL_CONTEXT': '#475563', 'MISSING': '#eeeeee'}
LABELS = {'WITHIN_PROPOSED_STEADY': 'Within Reference', 'STEADY_DEVIATION': 'Deviation',
    'NEW_STEADY_LEVEL': 'New steady level: review', 'UNSUPPORTED_TRANSITION': 'Transition unsupported',
    'STATE_GATE_EXCLUDED': 'SV excluded', 'DATA_UNAVAILABLE': 'Data quality',
    'UNSUPPORTED_CONTROL_CONTEXT': 'Control unsupported', 'MISSING': 'Missing observations'}


def load_case(name):
    return json.loads(gzip.decompress((OUT / f'{name}.json.gz').read_bytes()))


def style():
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
        'axes.spines.right': False, 'axes.titleweight': 'bold', 'figure.facecolor': 'white',
        'axes.labelcolor': '#263441', 'text.color': '#263441', 'axes.edgecolor': '#d1d7dc'})


def composition():
    style()
    result = json.loads((OUT / 'summary.json').read_text())
    cases = result['cases']
    fig, ax = plt.subplots(figsize=(13, 8.3), layout='constrained')
    y = np.arange(len(cases)); left = np.zeros(len(cases))
    for category in COLORS:
        values = np.array([c['missing_minutes'] if category == 'MISSING' else c['categories'].get(category, 0) for c in cases]) / 4320 * 100
        ax.barh(y, values, left=left, color=COLORS[category], label=LABELS[category],
            edgecolor='white', linewidth=.4, hatch='//' if category in {'MISSING', 'DATA_UNAVAILABLE'} else None)
        left += values
    ax.set_yticks(y, [c['title'] for c in cases]); ax.invert_yaxis(); ax.set_xlim(0, 100)
    ax.set_xlabel('Share of 4,320 planned synthetic minutes per case (%)')
    ax.set_title('Frozen Reference: 17 synthetic behavior cases', loc='left', pad=22)
    ax.grid(axis='x', alpha=.18); ax.set_axisbelow(True)
    fig.legend(*ax.get_legend_handles_labels(), loc='outside lower center', ncol=3, frameon=False)
    fig.suptitle('Virtual 7–9 Oct 2026 · 16 MX058/M1 cases + 1 MX017/M1 OFF-only case · not approval evidence',
        fontsize=10, y=1.02)
    fig.savefig(OUT / 'scenario-composition.png', dpi=140, bbox_inches='tight')
    return fig


def timeline(name, until=840):
    style()
    data = load_case(name); summary = data['summary']; model = json.loads((OUT / f'profile-{summary["machine"]}.json').read_text())
    date = data['chart'][0]['time'][:10]
    points = [p for p in data['chart'] if p['time'][:10] == date and 360 <= int(p['time'][11:13]) * 60 + int(p['time'][14:16]) <= until]
    x = np.array([int(p['time'][11:13]) * 60 + int(p['time'][14:16]) for p in points])
    chosen = set(model['reference_review']['accepted_regime_ids'])
    regimes = [r for r in model['regimes'] if r['regime_id'] in chosen and r['context'].endswith('_SV_OFF')]
    fig, axes = plt.subplots(3, 1, figsize=(12, 7.3), sharex=True,
        gridspec_kw={'height_ratios': [2.4, 2.4, 1.8]}, layout='constrained')
    for ax, field in zip(axes[:2], ('hp2', 'lp2')):
        index = PHYSICAL.index(field)
        lo = min(r['center'][index] - r['scale'][index] * r['threshold'] for r in regimes)
        hi = max(r['center'][index] + r['scale'][index] * r['threshold'] for r in regimes)
        ax.axhspan(lo, hi, color='#28759a', alpha=.12, label='Union of accepted OFF bounds*')
        values = [p['features'][field] if p['features'] else np.nan for p in points]
        ax.plot(x, values, color='#243c58', linewidth=1.5, label=f'{field.upper()} simulated')
        ax.set_ylabel(f'{field.upper()} (psi)'); ax.grid(alpha=.15)
        ax.legend(loc='upper left', frameon=False, fontsize=9)
        for e in data['controls']:
            if e['occurred_at'][:10] != date: continue
            at = int(e['occurred_at'][11:13]) * 60 + int(e['occurred_at'][14:16])
            ax.axvline(at, color='#765f9e', linestyle='--', linewidth=1)
    categories = [c for c in COLORS if c in {p['category'] for p in points}]
    for category in categories:
        xs = [v for v, p in zip(x, points) if p['category'] == category]
        axes[2].scatter(xs, [categories.index(category)] * len(xs), color=COLORS[category], marker='s', s=12)
    axes[2].set_yticks(range(len(categories)), [LABELS[c] for c in categories]); axes[2].set_ylim(-.5, len(categories)-.5)
    ticks = np.arange(360, until+1, 60)
    axes[2].set_xticks(ticks, [f'{v//60:02}:{v%60:02}' for v in ticks]); axes[2].set_xlabel(f'{date} virtual source-local time · Asia/Bangkok')
    axes[0].set_title(summary['title'], loc='left')
    fig.suptitle(f'{summary["machine"]}/M{summary["module"]} · frozen {summary["profile_id"][:12]} · MOCK / no source insertion', fontsize=10, y=1.02)
    fig.text(.01, -.10, '* Display-only union of per-channel bounds; the scorer checks all eight physical features against one accepted regime.\n'
        'Control markers are synthetic. New steady level requires review; a low flag rate does not make it Normal.', fontsize=9)
    fig.savefig(OUT / f'{name}-timeline.png', dpi=140, bbox_inches='tight')
    return fig


def main():
    result = json.loads((OUT / 'summary.json').read_text())
    cases = {c['case']: c for c in result['cases']}
    normal = sum(c['receipt']['supported_minutes'] for name, c in cases.items() if name.startswith('normal_regime_'))
    plateau = cases['cp2_plateau']['categories']
    summary = f'''# Frozen Context Reference — synthetic scenario QA

## tl;dr

Executed **17 cases / 73,260 synthetic observed minutes** against saved MX058/M1 and MX017/M1 frozen Profiles. All17 behavioral expectations passed; four accepted MX058 steady modes have **{normal:,} within-Reference minutes and zero flags**. In the six-hour/day CP2 raised plateau, **{plateau['NEW_STEADY_LEVEL']:,} minutes require new-level review** and12minutes are deviations. Stable values outside the Reference are not adopted as Normal. One-minute spikes are detected but the aggregate flag rate remains below1%.

Valve command alone does not create an anomaly. Delayed response remains unsupported because this MX058/M1 Profile has **no accepted Transition templates**. Real OFF-only MX017 abstains on excluded ON and evaluates the first returning OFF minute immediately.

These are software scenarios, not healthy/fault accuracy, real sensor data, elapsed future days or approval evidence. Source/Profile/review/Active/Event/job state was not written. No Mock button was added.
'''
    cells = [nbformat.v4.new_markdown_cell(summary), nbformat.v4.new_markdown_cell('''## Context & Methods

### Key Assumptions

- Seed58, three virtual complete days7–9Oct2026, one-minute synthetic observations with declared coverage60/60. No Raw seconds were generated or ingestion tested.
- Use actual saved accepted regimes and unchanged thresholds. Normal variation is fixed at0.04×local feature scale; HP2/LP2 tests use fixed ±60/±10psi shifts. This generator does not fit a model or claim those trajectories represent refrigeration physics.
- DP1/DP2 are always derived from HP−LP. Controls/events remain in memory and local files.
- `flag_pct` denominator is supported scored minutes; new levels/unsupported transitions are separate unresolved evidence. Missing/quality/manual states are not health claims. Aggregate metrics alone are not Active readiness.
- Source of parameters: localhost saved `ht9046mx_context_profile`; model/version/hash/settings receipts in `outputs/context_scenarios_20261006/summary.json`. Frozen exports allow rerun without live telemetry.
'''), nbformat.v4.new_code_cell('''from pathlib import Path
import sys, json, gzip
root = Path.cwd()
if not (root / 'apps').exists(): root = root.parent
sys.path.insert(0, str(root))
from notebooks.support.frozen_context_scenarios import OUT, build_cases, run_case
from notebooks.support.frozen_context_scenario_delivery import composition, timeline
from apps.api.app.config import get_settings
from apps.api.app.unified_events import fingerprint
import pandas as pd
from IPython.display import display, Image
import matplotlib.pyplot as plt
result = json.loads((OUT / 'summary.json').read_text())
settings = get_settings()
display(pd.DataFrame([{'Model': c['machine'], 'Profile': c['profile_id'][:12]} for c in result['cases']]).drop_duplicates())
'''), nbformat.v4.new_markdown_cell('''## Data

### Saved frozen inputs and exact rerun

The cell below reads the two locally exported frozen Profiles, re-generates all17cases, and checks their category counts, supported/unresolved minutes and flag rates against saved evidence. It performs no source database reads or writes. Current `.env` supplies the same contract/settings used by the application; never print secrets.
'''), nbformat.v4.new_code_cell('''expected = {c['case']: c for c in result['cases']}
checks = []
for machine, off_only in [('MX058', False), ('MX017', True)]:
    model = json.loads((OUT / f'profile-{machine}.json').read_text())
    assert fingerprint(model) == result['profile_hashes'][model['profile_id']]
    for case in build_cases(model, settings, off_only=off_only):
        fresh, points = run_case(case, model, settings)
        assert fresh['categories'] == expected[case['case']]['categories']
        assert fresh['receipt'] == expected[case['case']]['receipt']
        checks.append({'Case': case['case'], 'Observed minutes': len(points), 'Expectation': 'PASS'})
display(pd.DataFrame(checks))
print(f'{len(checks)} deterministic cases reproduced; {sum(c["Observed minutes"] for c in checks):,} observed minutes.')
'''), nbformat.v4.new_markdown_cell('''## Results

### 1. Category composition

Every row has4,320planned virtual minutes. The missing-data case has180missingminutes retained as gaps. Categories are mutually exclusive; supported day counts are not approval.
'''), nbformat.v4.new_code_cell('''figure = composition()
display(Image(filename=str(OUT / 'scenario-composition.png')))
plt.close(figure)
'''), nbformat.v4.new_markdown_cell('''### 2. Exact validation accounting

`Metrics only` checks the existing numerical conditions; it does not include source contracts, engineering review, included-state completeness or synthetic provenance. Every scenario is explicitly barred from approval.
'''), nbformat.v4.new_code_cell('''table = pd.DataFrame([{'Case': c['case'], 'Supported min': c['receipt']['supported_minutes'],
    'Flag min': sum(c['categories'].get(k, 0) for k in ['STEADY_DEVIATION', 'UNEXPECTED_TRANSITION']),
    'Flag %': round(c['receipt']['flag_pct'], 3), 'Unresolved min': c['receipt']['unresolved_minutes'],
    'Missing min': c['missing_minutes'], 'Metrics only': c['metrics_only_within_gate'], 'Approval evidence': False}
    for c in result['cases']])
display(table)
'''), nbformat.v4.new_markdown_cell('''### 3. Raised stable CP2 without a control transition

Pressure rises at07:00and stays high for six hours. Initial movement is a deviation; after the five-minute stability observation it becomes a new steady level requiring review. Nothing updates the frozen reference. Of1,080raisedminutes, allremain outside accepted Normal.
'''), nbformat.v4.new_code_cell("figure = timeline('cp2_plateau')\ndisplay(Image(filename=str(OUT / 'cp2_plateau-timeline.png')))\nplt.close(figure)"), nbformat.v4.new_markdown_cell('''### 4. Delayed pressure response after Valve command

Valve changes at06:59:30. Physical values remain within Reference until07:10, then rise. Normal initial values do not erase the control event. No accepted template exists in this actualProfile, so unsupported transition/new-level evidence blocks numerical acceptance. This is not proof the response is faulty or healthy.
'''), nbformat.v4.new_code_cell("figure = timeline('valve_delayed_response', until=600)\ndisplay(Image(filename=str(OUT / 'valve_delayed_response-timeline.png')))\nplt.close(figure)"), nbformat.v4.new_markdown_cell('''### 5. Excluded SV ON and immediate return check

The actual saved MX017/M1 OFF-only review is used without editing its scope. ON07:00–08:00is excluded while raw feature evidence remains in this QA file. The first OFF minute at08:00is evaluated and flagged when still outsideReference; there is no cooldown.
'''), nbformat.v4.new_code_cell("figure = timeline('excluded_on_return_outside', until=600)\ndisplay(Image(filename=str(OUT / 'excluded_on_return_outside-timeline.png')))\nplt.close(figure)"), nbformat.v4.new_markdown_cell('''## Takeaways

- Normal at all four accepted MX058 levels remains withinReference; command changes alone are not physical anomalies.
- A stable abnormal plateau does not disappear: `NEW_STEADY_LEVEL` creates unresolved review evidence even when aggregate `flag_pct` is small.
- A1-minute spike is detected, but3minutes across4,320minutes gives0.0695%, under the current1%aggregate threshold. This Profile acceptance statistic is not a statement that the spike is safe, nor an operational episode alert guarantee.
- Missing ON/Transition Reference requires coverage/review, not a blanket delay or automatically treating those observations asNormal. ExcludedON retains evidence and returningOFF is checked immediately.
- Missing/bad-quality/manual-control cases can have numerically lowflags because those minutes are not scored. Inspect daily quality/missing/unsupported counts; never read lowflags as certification.
- All17cases areMOCK/nonprospective and cannot createActive. Actual source afterfreeze, Raw/ingestion/manual realfuture acceptance and verified engineering/contracts remain untested by these synthetic scenarios.
''')]
    book = nbformat.v4.new_notebook(cells=cells, metadata={'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}})
    nbformat.validate(book)
    NotebookClient(book, timeout=180, kernel_name='python3', resources={'metadata': {'path': str(ROOT)}}).execute()
    nbformat.write(book, BOOK)
    from nbconvert import HTMLExporter
    html, _ = HTMLExporter(template_name='lab').from_notebook_node(book)
    (OUT / 'notebook-preview.html').write_text(html, encoding='utf-8')
    print(BOOK)


if __name__ == '__main__':
    main()
