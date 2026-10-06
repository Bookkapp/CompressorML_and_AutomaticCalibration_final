"""Build owner-facing receipts from executed local analysis and QA files."""
import csv,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'notebooks/outputs/sv_comparison_20261004'

def make():
    cover=list(csv.DictReader((OUT/'coverage.csv').open(encoding='utf-8')))
    shifts=list(csv.DictReader((OUT/'feature_shifts.csv').open(encoding='utf-8')))
    rows=[]
    for c in cover:
        machine,module=c['machine'],int(c['module'])
        def delta(feature):
            item=next((x for x in shifts if x['machine']==machine and int(x['module'])==module and x['feature']==feature),{})
            return float(item['matched_median_delta']) if item.get('matched_median_delta') else None
        rows.append({'machine':machine,'module':module,'matched_on_minutes':int(c['matched_on_minutes']),'unique_off_controls':int(c['unique_off_controls']),'matched_days':int(c['matched_days']),'hp2_delta_psi':delta('hp2'),'temp_low_delta_c':delta('templo')})
    source={'label':'Actual 017/024 dynamic telemetry, 17–30 Sep 2026','files':[{'label':x} for x in ['28 original dynamic daily CSVs in ZIPs; SHA256 inventory in receipt.json','coverage.csv','feature_shifts.csv','receipt.json']],
        'filters':['Asia/Bangkok; observed seconds → screened minute means','Same machine, module, day; nearest SV Off within 60 minutes','Run + module On + Busy 0; pure SV On/Off; ≥57 unique seconds; no duplicate seconds; gap ≤5 s; finite sensors'],
        'caveats':['Off controls are reused; matched minutes are not independent trials.','State/recipe transitions can confound this observational comparison; no causal effect or healthy equivalence is established.','M7 has raw rows but no qualifying comparison minutes. No gate was relaxed.'],
        'metricDefinitions':[{'label':'Matched delta','definition':'Median of (SV On minute mean − nearest matched SV Off minute mean), separately for each machine/module.'}]}
    receipt={'schemaVersion':1,'items':[{'id':'sv-on','title':'SV On เปลี่ยนค่าเทียบกับ SV Off มากแค่ไหน?','assumptions':['Pressure psi is owner-confirmed; gauge/absolute basis is still unverified.'],'queries':[{'id':'sv-matched','source':source,'sourceRoles':[{'kind':'file','label':'feature_shifts.csv','role':'Executed observed-data comparisons; not synthetic examples.'}],
        'reportingPeriod':'17–30 September 2026; end exclusive 1 October','columns':list(rows[0]),'rows':rows,'methods':[{'language':'calculation','code':'Match each screened SV On minute with the nearest SV Off minute on the same machine/module/local day within 60 minutes.\nReport median (On − Off) and P95 absolute difference per feature.\nExecuted: 09_SV_On_Comparison_20261004.ipynb; 196 SV On Hp2 minute-mean checks matched original observed seconds.'}]}]}]}
    (OUT/'inline-sources.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    table='\n'.join(f"| {r['machine']}/M{r['module']} | {r['matched_on_minutes']} | {r['unique_off_controls']} | {r['matched_days']} | {r['hp2_delta_psi']:+.3f} | {r['temp_low_delta_c']:+.3f} |" if r['hp2_delta_psi'] is not None else f"| {r['machine']}/M{r['module']} | 0 | 0 | 0 | ไม่พอ | ไม่พอ |" for r in rows)
    audit=json.loads((OUT/'final-audit.json').read_text())
    jobs=[]
    for machine in ('MX017','MX024'):
        r=next(j for j in audit['jobs'] if j['machine_number']==machine)
        jobs.append(f"- {machine}: {r['status']}, job `{r['job_id']}`, {r['profiles']} Candidates; {r['created_at']} → {r['updated_at']} UTC.")
    load=json.loads((OUT/'raw-load.json').read_text());parity=json.loads((OUT/'selector-parity.json').read_text())
    report=f'''# Calibration evidence, automatic Reference and SV review — 4 October 2026

## Scope and outcome

Owner-authorized local Operation changes; source SELECT only. Workflow preparation and evidence-copy actions were actual browser clicks. SQL/GET checks below are technical diagnostics. Pressure unit is now owner-confirmed **psi**, recorded in the local central configuration. Gauge/absolute basis and state/controller/service versions remain unverified. No automatic Active promotion; manual approval rules remain.

The web now explains Reference, held-out Shadow and shared prerequisites separately. Review Required does **not** always mean changing the Reference period. Shadow changes require investigation; source prerequisites require verified configuration. Readable statuses, actual values/limits, drift evidence, contributor intervals and minute/observed-second navigation replace unexplained codes. Existing frozen estimator, thresholds, gate and source rows are preserved.

## SV comparison

Original dynamic ZIP daily CSVs: **28 files / 2,385,588 observed rows**, two machines/all eight modules, **17–30 Sep 2026** (`[17 Sep, 1 Oct)`), Asia/Bangkok. All file hashes/inventories are recorded in `notebooks/outputs/sv_comparison_20261004/receipt.json`. Static excluded. Actual source state counts for all 28 files and **196 SV On Hp2 minute means** were reconciled to the audited minute evidence.

Comparison uses finite sensors, nonnegative Valve, ≥57 unique seconds, no duplicate seconds, gaps ≤5s, stable Run/module On/Busy0 and pure SV On or Off throughout each minute. Each On minute is matched to nearest Off on the same machine/module/day within60min. Off controls are reused, so these are not independent trials, a randomized causal study or an equivalence test. Neither state is labelled healthy.

| Machine/module | Matched On minutes | Unique Off controls | Days | Median Hp2 On−Off (psi) | Median TempLow On−Off (°C) |
|---|---:|---:|---:|---:|---:|
{table}

**Decision:** retain SV Off eligibility for the existing Cold baseline. Some pressure medians move little, but temperatures and tails still move substantially. E.g.017/M8 Hp2 median−3.266psi while TempLow+11.917°C; P95 absolute differences21.469psi/78.938°C. Do not infer non-running/Hot solely from SV On: actual Run/moduleOn/Busy0 co-occurrence is observed. Dedicated On or recipe-conditioned profiles require separate evidence and validation. All states remain visible in Raw review; no source rows are deleted.

## Automatic proposal and performance

Version `past-only-reference-proposal-v1`: search only the configured already-read Reference history, normally28days. Blocks7/14/21/28days with0/7/14/21day backtracks, bounded16 possibilities; current28day context has10. Keep complete days before fixed held-out Shadow. Existing retained minima/quarantine/drift/positive-threshold checks plus proposal-only daily-level-span≤2.0 compare between-day levels with within-day robust variation. Rank passing blocks by continuity, qualified days, recency and quarantine. No automatic exclusions; no Shadow feedback; no retry-until-pass. If none pass, preserve the default period and mark for review. Stable does not certify healthy. Verified service-epoch segmentation is **not implemented** because source repair epoch data are unverified.

Vectorized proposal yields exact full-result equality to the prior implementation on017/M1,M8 and024/M1,M6 (each≈40,320 cached windows). Proposal time ranges {min(x['old_seconds'] for x in parity):.3f}–{max(x['old_seconds'] for x in parity):.3f}s before, {min(x['vector_seconds'] for x in parity):.3f}–{max(x['vector_seconds'] for x in parity):.3f}s after. This measures proposal computation, **not** total raw history preparation latency. Saved comparison implementation and receipt support reproduction.

Source validation/reading31historical days is still expensive on this local8GBmachine:017 preparation took701.743s. Jobs run durably in the background; old evidence remains accessible during preparation. Closed-day cacheTTL1hour and fresh source-digest checks on Manual Build remain. Per-profile persisted Reference boundaries now match each selected module's reviewed period; batch scope remains the search envelope.

Raw GET: actor/job-scope authorization before cache; minute-aligned bounds within saved review, maximum30minutes/6000rows; excess fails explicitly. SQL retains all states. Two source readers, coalesced identical requests, eight-slice60sec cache, fixed230px graph, no interpolation across gaps. Hourly/minute graphs are loaded on demand; evidence intervals bounded200 with explicit truncation, exact minute score/threshold and dominant contributor.

## Actual UI and load QA

{chr(10).join(jobs)}

- 017/M1: click TempLow interval29Sep23:35→23:40 → matching day/thermal feature ±30min view → Raw296rows/296distinct seconds/300expected, no duplicates, SVOff296; score view present. Saved `shadow-raw-evidence.png`.
- 024/M1: custom Raw19Sep05:28→05:38 →592rows/591distinct seconds/600expected, duplicate-affected rows2, SVOff120/On472. Saved `raw-sv-review.png`.
- 024/M7: actualUI0qualified/44,640observedminutes; prioritized reasons42,130module-not-stable-On,1,344duplicate-minute,1,146global-not-stable-Run,20low-coverage. Build disabled; all-state Raw remains available.
- Invalid70minute custom request rejected in UI with readable30minute limit. Existing graph retained. User-selected period is never silently broadened.
- Desktop1280×900 and narrow603px layouts checked; desktop cards do not overflow (client/scroll widths1265px). Temporary viewport override reset afterQA. No fabricated successful Active path.
- Raw read load: **{load['clients']} clients / {load['requests']} GETs / {load['success']} successful**, p50{load['p50_ms']:.1f}ms, p95{load['p95_ms']:.1f}ms, max{load['max_ms']:.1f}ms. Cached ten-minute slice of592actual rows; not a cold full-history or Server SLA.
- Final backend **167 full-suite tests passed**, then the11-test evidence suite including one additional saved-quarantine-policy regression passed; frontend production build passed (existing large-bundle warning810.20kB/233.86kB gzip); diff whitespace check passed. Source SHA/reviewer/queue/copy/raw range/auth/coalescing/past-only split and per-module persistence tests included.
- Active pointer count **{audit['active_count']}**, SHA256 `{audit['active_sha256']}` matches pre-work snapshot. No source DML, no Active approval, no normal detector/ML job activation, no target Server deployment or Git push.

## Reproduction / remaining limits

From repository root: `python -m notebooks.support.sv_on_comparison`, `python notebooks/support/calibration_evidence_qa.py parity`, `python notebooks/support/calibration_evidence_qa.py load`, `python notebooks/support/calibration_evidence_qa.py audit`, `python -m pytest apps/api/tests -q`; `apps/web`: `npm run build`. Analysis notebook09 and source receipts contain actual executed results. LocalRaw is read-time context, not an immutable source snapshot; final Manual Build still rechecks source. Historical profiles/jobs remain immutable and may still show previous unverified-unit state. Production clock/auth/resource/worker acceptance and a genuinely eligible human-approved Active flow remain unverified.
'''
    (ROOT/'deployment/CALIBRATION_EVIDENCE_AND_SV_REVIEW_20261004.md').write_text(report,encoding='utf-8')
    print('Receipt and report written from actual analysis/QA records.')

if __name__=='__main__':make()
