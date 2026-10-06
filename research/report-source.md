# Research Source Notes — HT9046MX Predictive Maintenance Thesis

**2026-10-01 supplement:** Control-state/EEV/multimode review uses current code and previously executed MX017/024/080 July–1 Oct evidence; historical 19-machine scope below is not the sole current evidence. Detailed access status, bibliography and model-to-system mapping are in `HT9046MX_CONTROL_STATE_AND_ANOMALY_RESEARCH_20261001.md`. Current primary remains rule-only robust z/persistence; proposed event ARX/DPCA is not implemented. Public share and exact installed MX manual access remain incomplete.

**Created:** 2026-09-08
**Audience:** Technical project owner, refrigeration SME, data/ML engineer, model reviewer and production approver
**Research question:** Given the actual coverage and limitations of HT9046MX telemetry, what analysis, modeling, parameter-search, Auto-bootstrap, QA and deployment architecture is technically defensible and can progress toward Production?

## Scope and assumptions

- System semantics are governed by `README_System.md`.
- Internal empirical evidence covers 19 machines and data from 2026-08-04 through 2026-09-01.
- The current objective is condition monitoring and screening, not automatic confirmation of refrigerant leakage and not autonomous machine control.
- Research covers vapor-compression FDD, industrial multivariate time-series anomaly detection, dynamic residual modeling, cross-machine validation, drift, threshold calibration, explainability and governance.
- Literature from other refrigeration architectures is used as methodological evidence, not as proof that HT9046MX has identical fault signatures.
- No production accuracy claim is possible without technician-confirmed outcomes.

## Direct answer


The current data can support Production engineering for a shadow or technician-advisory anomaly-screening service. It cannot yet support a defensible claim of automatic leak diagnosis. Research on production ML consistently shifts attention from a model file to the surrounding data validation, split isolation, monitoring, versioning, human review and rollback system. Recent anomaly-detection benchmarks also weaken any argument that a Transformer or LSTM should be preferred by default; simpler/statistical baselines must remain in every matched comparison.

## Evidence gap matrix

| Claim family | Evidence | Confidence | Contradiction/limitation | Remaining gap |
|---|---|---|---|---|
| Conditional baselines are necessary | Internal between/within ratios; refrigeration FDD literature conditions normal performance on driving conditions | High | Recipe, load and water context absent | Add historian context |
| High-side pressure and water context require directional evidence | Danfoss water-cooled condenser troubleshooting plus MX-080 MessageLog audit | Medium | General documentation does not expose HT9046-MX piping/control; no synchronized water telemetry | Collect inlet/outlet temperature, flow/pressure, tank level and alarm codebook |
| Isolation Forest is a useful first detector | Original algorithm; low-memory implementation; internal temporal/LOMO screening | Medium-high | Point/tabular detector does not model full dynamics | Compare ARX and sequence challenger on labeled events |
| TCN is a credible sequence challenger | Sequence-model comparison literature and recent industrial case evidence | Medium | Generic benchmarks are not HT9046MX | Run matched TCN-AE vs LSTM-AE experiment |
| ARX residual modeling is relevant | Chiller/refrigeration FDD research used ARX with SVM and few variables | Medium-high | HT9046MX has cascade and controller-specific behavior | Identify stable input/output lags per state |
| Auto-bootstrap must resist contamination | Phase-I/Phase-II control-chart research; current absence of labels | High | Universal minimum sample count does not exist | Validate readiness thresholds with replay |
| Drift should trigger review/rebootstrap | ADWIN research; service/refill changes baseline | High | Drift may be load/recipe/sensor, not maintenance | Add service and operating-context logs |
| Alert thresholds need explicit false-alarm control | Conformal event anomaly research and operations requirement | Medium-high | Time dependence can violate exchangeability | Use blocked calibration and empirical machine-day alert budget |
| Random validation is insufficient | Time-series and cross-machine domain-shift research | High | LOMO groups remain small for some machines | Accumulate more machine-days and events |
| Human approval and documentation are required | NIST AI RMF; domain safety context | High | Governance framework is general, not refrigeration-specific | Define local approver and runbook |
| HPO can overfit validation even without label leakage | Random Search, Hyperband, Optuna/SMAC and model-selection-bias research | High | Unsupervised objective cannot measure leak accuracy | Nested inner temporal/group search; freeze outer tests |
| Deep anomaly benchmark gains may be unreliable | UCR benchmark audit, TimeSeAD, Schmidl evaluation, TSB-AD | High | Public benchmarks differ from this machine | Matched internal protocol; no point adjustment |
| Parameter-light ECOD/COPOD deserve comparison | Original ECOD/COPOD methods | Medium | Tabular outlier detection does not model temporal order | Feed state-conditioned relative/response features |
| RRCF is a plausible streaming challenger | Original RRCF stream paper | Medium | Online adaptation may absorb developing faults | Shadow only; frozen/reference window policy |
| Matrix Profile can expose unusual cycle morphology | Original Matrix Profile paper | Medium | Requires comparable, segmented cycles | Offline forensic lane after recipe/state segmentation |
| Production readiness is a system property | Data Validation for ML, ML Test Score, Hidden Technical Debt, production pipeline studies | High | General ML systems evidence | Map into local SLO, registry, rollback and QA gates |
| Weak supervision can scale expert rules but is not truth | Snorkel and interactive time-series weak-supervision work | Medium-high | Label functions may be correlated and encode existing rules | Keep technician gold set and abstain/ambiguity class |

## Research waves

1. Refrigeration FDD: fault signatures, steady-state qualification, virtual sensors, leakage and charge diagnosis.
2. Statistical and shallow anomaly modeling: robust residual, EWMA/CUSUM, ARX, PCA, Isolation Forest, ECOD/COPOD and RRCF.
3. Sequence/subsequence modeling: LSTM-AE, TCN-AE, Anomaly Transformer, TranAD, MEMTO and Matrix Profile.
4. Benchmark integrity: UCR benchmark audit, Schmidl 71-method evaluation, TimeSeAD, TSB-AD and range/event metrics.
5. Auto-bootstrap and uncertainty: Phase-I contamination, moving/stationary block bootstrap, conformal methods for dependent data, drift and service epochs.
6. HPO: Random Search, Hyperband, Optuna, SMAC3 and model-selection bias.
7. Label strategy: weak supervision, technician gold labels, active review and ambiguity/abstention.
8. Production systems: data validation, ML Test Score, hidden technical debt, production pipelines, registry, inference runtime and observability.

## Synthesis decisions

- Prioritize evidence that matches field data, multivariate telemetry and limited labels.
- Down-weight laboratory classification results when fault classes were artificially imposed and train/test records came from the same equipment.
- Treat new 2026 preprints as directional evidence only.
- Preserve a separate fault-confirmation path through maintenance inspection.
- Treat Auto-bootstrap profile, statistical bootstrap, model bagging and AutoML/HPO as four distinct mechanisms.
- Keep outer temporal/LOMO/sparse tests untouched by feature, parameter and threshold selection.
- Consider shadow/advisory screening a separate and earlier production capability than diagnostic automation.

## Search and source-selection notes

- Searches were conducted on original publisher/proceedings pages and official technical documentation as of 2026-09-08.
- Primary sources were preferred: International Journal of Refrigeration, JMLR, PMLR/ICML/COLT, PVLDB, NeurIPS, ICLR/OpenReview, IEEE, NIST, Google Research and official tool documentation.
- Secondary reviews were used only for landscape context; machine-specific conclusions were not taken from reviews.
- Papers reporting high accuracy on laboratory or public benchmarks were not used to claim HT9046MX accuracy.
- Current tool documentation was used only for capabilities and operational cautions, not to establish scientific superiority.
- Exact source-to-claim mappings are maintained in `claim-to-source-ledger.md`.

## Research stop rationale

The central recommendations are supported by multiple independent source classes: original refrigeration FDD research, original anomaly/drift methods, independent benchmark audits, industrial domain-shift studies, official statistical guidance, production-ML studies and the project's own reproducible outputs. The last search waves concentrated on contradictory evidence and production failure modes; they strengthened the shallow-hybrid-first recommendation and did not identify evidence that would justify immediate LSTM/Transformer deployment. Remaining uncertainty now depends mainly on new HT9046MX labels, operating context, Auto-bootstrap replay and shadow evidence rather than more generic literature.

## Change log

- 2026-09-08 — Expanded to eight research waves; added HPO, benchmark integrity, weak supervision, production systems and explicit production-feasibility synthesis
- 2026-09-08 — Clarified Loop Check as repeated QA review and removed the unintended duplicate-system interpretation
