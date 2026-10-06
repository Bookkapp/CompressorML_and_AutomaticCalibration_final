# External intake chart and QA plan — 2026-09-10

Surface: self-contained Python/Colab notebook, with exported PNG figures.
Sources: external source manifest, audited novel rows, daily state-qualified sample summaries,
and EDA quality minutes with an additional three-minute context continuity check.

| Question | Figure | Grain and context | Interpretation limit |
|---|---|---|---|
| Which dates add coverage? | Calendar strip by machine | One mark per actual daily source file; six machines | ZIP contents separate until audited; gaps remain visible |
| How much is additional? | Horizontal stacked bars from zero | Novel versus primary-overlapping wide rows | Count reconciliation required; neither count is a healthy-label count |
| How do levels differ? | Annotated machine-module heatmap | Median of daily Hp_2nd medians, SV Off, day count in each cell | Equal-day weighting; not a pooled-second median or approved baseline |
| Are levels stable over time? | Eight-module small multiples for each machine | Daily median split by SV; full date axis with missing days | Common y range includes all plotted values; 200 is only screening reference |
| Do associations differ? | Two annotated correlation matrices | Spearman Valve/Lp_2nd, module and SV; >=200 minute pairs | No causal/lag inference; sample/day table retained; undefined constant strata blank |

Palette: blue/gold for discrete context and source overlap, grey text/references;
single blue sequential heatmap; purple/orange for signed correlation with numeric labels.
No red/green fault classification. Fonts remain readable at notebook width (11–14 inches).
Inspect exported calendar, heatmaps and representative small multiples before handoff.

Execution QA: v2 renders all six machine time-series panels, the Hp_2nd heatmap, the two-SV correlation heatmap and a selected seven-sensor matrix. Correlations resolve for 83 of 87 available contexts; blanks honestly represent insufficient/constant strata.
