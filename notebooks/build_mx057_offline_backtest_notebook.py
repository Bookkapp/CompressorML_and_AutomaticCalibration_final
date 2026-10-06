"""Build a compact, executed companion notebook for the MX057 backtest."""

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "notebooks" / "outputs" / "mx057_offline_calibration_backtest_v4_confirmed_state"
NOTEBOOK = ROOT / "notebooks" / "10_MX057_Offline_Calibration_Backtest.ipynb"

nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell(
        "# MX057 — Offline Calibration Backtest\n\n"
        "## tl;dr\n"
        "This is a read-only historical replay: 62 source days from 12 May to 9 Aug 2026, "
        "with 7–9 Aug reserved as a forward-only shadow period. The partial 10 Aug export is excluded. "
        "No Server, MySQL analytics table, Active Profile or machine-control path was used.\n\n"
        "The current replay applies the owner-confirmed Cold gate: Compressor ON, `Status_n=On`, `Busy=0`, and `SV=Off`. "
        "The result is a calibration-gate test, never a fault conclusion."
    ),
    nbf.v4.new_markdown_cell("## Context & Methods\n\n"
        "**Grain:** raw one-second handler logs are aggregated to stable one-minute windows. "
        "**Timezone assumption:** Asia/Bangkok; source exports do not encode a timezone. "
        "**Profile key:** Machine × Module × SV × qualified state. **Current eligible state:** Compressor ON + `Status_n=On` + `Busy=0` + `SV=Off`. "
        "The candidate fits median/MAD-style robust local statistics on history, then shadows the final three days. "
        "Red points only mean score above a local candidate threshold; they are not confirmed equipment faults.\n\n"
        "### Key assumption\nThe 28-day gap between the May and late-June extracts is retained as a provenance limitation; it is not imputed."
    ),
    nbf.v4.new_code_cell(
        "from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import display, Image\n\n"
        "artifact = Path('outputs/mx057_offline_calibration_backtest_v4_confirmed_state')\n"
        "summary = json.loads((artifact / 'summary.json').read_text(encoding='utf-8'))\n"
        "profiles = pd.read_csv(artifact / 'profile_summary.csv')\n"
        "summary"
    ),
    nbf.v4.new_markdown_cell("## Data quality and profile gates"),
    nbf.v4.new_code_cell(
        "display(profiles[['module','sv_state','status','reasons','calibration_windows','shadow_windows',\n"
        "                  'quarantine_pct','shadow_flag_pct','persistent_flag_pct','shadow_elapsed_hours']])"
    ),
    nbf.v4.new_markdown_cell("## Shadow score graph\n\n"
        "Blue is below the candidate threshold. Red is above it. The dashed line is each profile's local threshold. "
        "Different panels intentionally have different y-scales, so use them to inspect movement inside a module rather than compare score magnitudes across modules."
    ),
    nbf.v4.new_code_cell("display(Image(filename=str(artifact / 'mx057_shadow_scores.png')))") ,
    nbf.v4.new_markdown_cell("## Takeaways"),
    nbf.v4.new_code_cell(
        "display(pd.Series(summary['profiles']).to_frame('value'))\n"
        "display(profiles[['module','sv_state','state_code','status','reasons']])\n"
        "print('Interpretation: only the owner-confirmed Cold state is eligible. No approval dry-run is an activation. "
        "Before Server staging, source machine_number × recorded_at must be unique; the worker fails closed if it is not.')"
    )
]
nb.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}
nbf.write(nb, NOTEBOOK)
print(NOTEBOOK)
