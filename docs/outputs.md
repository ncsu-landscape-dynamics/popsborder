# Outputs

## Item and box pretty printing

Pretty printing of individual consignments and items can be enabled by `--pretty`
in the command line with output like this:

```text
━━ Consignment ━━ Boxes: 3 ━━ Items: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛 ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛 | ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Consignment ━━ Boxes: 2 ━━ Items: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Th above is the default output (equivalent with `--pretty=boxes`). Separation of
individual boxes can be disabled using `--pretty=items` where the only unit
shown graphically are the items. Possible output looks like this:

```text
━━ Consignment ━━ Boxes: 3 ━━ Items: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Consignment ━━ Boxes: 2 ━━ Items: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Finally, option `--pretty=boxes_only` focuses just on the boxes and does not
show individual items:

```text
── Consignment ── Boxes: 6 ── Items: 60 ───────────────────────────────────
🐛 🐛 ✿ ✿ ✿ 🐛
── Consignment ── Boxes: 4 ── Items: 40 ───────────────────────────────────
✿ ✿ ✿ 🐛
```

This can be further configured using `pretty` key in the configuration file:

```yaml
pretty:
  flower: o
  bug: x
  horizontal_line: "-"
  box_line: "|"
  spaces: false
```

Configuration like the above can allow you to use `--pretty` even when Unicode
characters are properly displayed in your terminal. Note that some characters,
such as the dash (`-`) above, need to be in quotes because they have a special
meaning in YAML.

The output with the settings above will look like:

```text
-- Consignment -- Boxes: 4 -- Items: 40 -----------------------------------
xooooooooo|ooooooxooo|oooooooooo|xoooooooox
-- Consignment -- Boxes: 6 -- Items: 60 -----------------------------------
xxooooooxx|oooooooooo|oooxooooxx|ooooooooxo|ooooxooooo|ooooxoooox
```

## Output details of items and indexes inspected

Alternatively, if you want to plot and further analyze the simulated consignments
and inspections, use `detailed=True` in the `run_scenarios()` function to
return an object with arrays of items (binary values representing contaminated or
not) and the item indexes inspected. If multiple simulation iterations
are being used, the details from the first simulation will be used.

```python
num_consignments = 10
results, details = run_scenarios(
    config=config,
    scenario_table=scenario_table,
    seed=42,
    num_simulations=1,
    num_consignments=num_consignments,
    detailed=True,
)
```

See the `scenarios` documentation and the validation plots Jupyter notebook
(validation_plots.ipynb) for further details on how to use `run_scenarios()` and
the details object. The items and inspected indexes are visualized in the
notebook to confirm that the consignment are being contaminated and inspected as
configured.

If using a command line interface to run the simulation, the flags `--detailed`
or `-d` can be used to print the details object in the terminal. However, using
the details object in the terminal is not recommended as it includes the items
and indexes inspected for the entire simulation and may be very large.


## Replication level output tracking
Outputs specific to the Plant Inspection Station (PIS) case study are managed by the `PISSimData` class
found in `popsborder/outputs.py`. The class centralises all replication‑level
data collection and provides utilities for persisting synthetic datasets.

### Purpose
`PISSimData` gathers the synthetic PIS records,
Risk‑Based Sampling (RBS) calculator data, consignment‑level summaries, and
commodity‑line inspection results generated during a simulation run. It
supports multiple replications by keeping an independent output directory for
each replication.

### Required inputs
* **`output_dir_rep`** – Path to a directory where CSV files for the current
  replication will be written. The directory is created automatically if it does
  not exist.
* **`config`** – Full simulation configuration dictionary. Only the
  `config["consignment"]["generation_method"]` block is consulted; when the
  generation method is `"input_file"` and the input file type is `"PIS"`,
  the class loads the provided PIS CSV into `self.pis_synthetic_data`.

### Core attributes & constants
* **`PIS_COLUMNS`**, **`RBS_COLUMNS`**, **`CONSIGNMENT_COLUMNS`** – Column
  specifications for the CSV outputs.
* **`OUTPUT_FILENAMES`** – Mapping of dataset keys (`consignments`,
  `pis`, `rbs`, `commodity_line_results`) to default filenames.

### Interpreting the outputs
| CSV file | Description                                                                                                                                       |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------|
| **synthetic_consignment_data.csv** | One row per consignment with aggregated infestation metrics (total plants, number of infested risk/inspection units, etc.).                       |
| **synthetic_pis_data.csv** | Raw PIS detection records for each inspection unit (inspection number, risk unit, sample counts, infection flags, action taken).                  |
| **synthetic_rbs_calc_data.csv** | RBS calculation inputs per risk unit (for more information on risk units see the `What a risk unit represents` section in `docs/consignments.md`) |
| **synthetic_commodity_line_results_data.csv** | Commodity‑line level inspection results.                                                                                                          |

The `get_summary_stats()` helper provides quick insight into how many
records were produced in a given  replication, which is useful for sanity‑checking of larger
simulation runs.

### Example usage
```python
from popsborder.outputs import PISSimData

sim_data = PISSimData(output_dir_rep="outputs/rep1", config=config)
# ... run simulation, adding consignments and inspection results ...
sim_data.finalize_dataframes()
sim_data.write_synthetic_data_to_csv()
stats = sim_data.get_summary_stats()
print("Records written:", stats)
```

This snippet demonstrates the typical workflow: instantiate the class,
populate it during the simulation, finalize the DataFrames, write CSVs, and
inspect the summary statistics.

## Replication level post-processing
The script provided in `slippage_model_utils/output_post_processing.py` can be used to
read in and post-process the replication-level outputs described above.

### Purpose
The script reads the replication‑level CSV files generated by `PISSimData` (the
`synthetic_commodity_line_results_data.csv` files inside each replication
folder) and derives high‑level slippage and efficiency metrics. It then
produces a series of diagnostic outputs:
* a consolidated CSV that combines every replication,
* a set of box‑plots, scatter plots and confidence‑interval plots,
* statistical‑test results (ANOVA, paired t‑tests),

These are useful for comparing alternative model
configurations (the *experiments*), assessing inspection coverage versus
slippage, and preparing figures for reports or publications.

### Configuration & required inputs
The script contains a small block of **user‑configurable constants** 
near the top of the script:

| Constant | Meaning                                                                                                                                                                                                       |
|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `DEFAULT_COLS` | Columns read from each replication CSV (inspection_number, risk_unit_id, …).                                                                                                                                  |
| `EXPERIMENT_ROOT` | Root folder that holds the experiment directories (this should be updated based on where you have stored/moved your replication outputs).                                                                     |
| `EXPERIMENTS` | List of experiment sub‑folders to process (e.g. `["Baseline", "Model_1", "Model_2"]`). These folders should contain the replication folders generated by the `PISSimData` class (e.g., `rep_0`, `rep_1`,...). |
| `POST_PROC_OUTPUT` | Destination directory for all post‑processing generated files.                                                                                                                                                |

The **runtime inputs** are the same values that can also be supplied via the CLI:

* `base_path` – path to the directory that contains the experiment folders
  (normally `EXPERIMENT_ROOT`).
* `experiments` – list of experiment names to analyse (defaults to
  `EXPERIMENTS`).
* `--cols` – optional override of `DEFAULT_COLS`.
* `--output-dir` – where plots and CSV files will be written (defaults to
  `POST_PROC_OUTPUT`).
* `--steps` – optional list of processing steps to run; if omitted the script
  executes **all** steps.  This can be used if not all statistical tests and or plots are needed
  (a user would specify what would like to be generated here).

### Expected outputs
When the script runs with the default step set, the following artefacts appear
under `POST_PROC_OUTPUT` (or the directory passed via `--output-dir`):

| Artefact | Description                                                                                                                                                                                                                            |
|----------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `replication_level_slippage.csv` | Consolidated table – one row per inspection unit across **all** replications, enriched with the slippage metrics.                                                                                                                      |
| `post_processing/box_slippage.png` | Box‑plot of total slipped plants per replication (linear scale).                                                                                                                                                                       |
| `post_processing/box_slippage_log.png` | Same box‑plot on a log‑scale (useful for heavy‑tailed distributions).                                                                                                                                                                  |
| `post_processing/scatter_replication.png` | Scatter of inspected sample units vs. slipped plants (log‑scaled y‑axis).                                                                                                                                                              |
| `post_processing/scatter_average.png` | Mean inspected units vs. mean slipped plants per experiment (with error bars).                                                                                                                                                         |
| `post_processing/scatter_average_custom.png` | Customized version matching the mean inspection units vs. mean slipped plants provided in the RBS impact assessment (report delivered to RBS team August, 2026).  This was a version of the same plot as above **without** error bars. |
| `post_processing/box_<metric>.png` | Box‑plots for each efficiency metric (`slip_per_inspected`, `inspected_per_slip`, `efficiency_score`, `slip_to_coverage`).                                                                                                             |
| `post_processing/efficiency_totals_ci.png` | Mean `slip_per_inspected_total` per experiment with 95 % confidence interval.                                                                                                                                                          |
| `post_processing/exported_results/summary.json` | JSON file summarising paths to all generated files and scalar results (ANOVA p‑value, t‑test tables, etc.).                                                                                                                            |
| `post_processing/exported_results/*.csv` | CSV exports of every intermediate DataFrame stored in the result dict (e.g. `total_slippage.csv`, `efficiency_totals.csv`).                                                                                                            |

### Example usage
Programmatic (typical from a notebook or another Python script):

```python
from slippage_model_utils.output_post_processing import run_post_processing
EXPERIMENT_ROOT = "<HOME>/results"
DEFAULT_COLS = "<RECOMMEND KEEPING THE SAME AS INDICATED IN THE SCRIPT>"
POST_PROC_OUTPUT = "<HOME>/post_processing"

results = run_post_processing(
    base_path=EXPERIMENT_ROOT,          # repository‑specific root
    experiments=["Baseline", "Model_1", "Model_2"],
    cols_of_interest=DEFAULT_COLS,
    output_dir=POST_PROC_OUTPUT,        # plots & CSV will go here
    steps=None,                         # run every step
)

print("ANOVA p‑value:", results["anova_p"])
print("Plots saved to:", POST_PROC_OUTPUT)
```

Example command‑line (the script provides a CLI wrapper):

```bash
python -m slippage_model_utils.output_post_processing \\
    "$HOME/results" \\
    Baseline Model_1 Model_2 \\
    --output-dir "$HOME/post_processing" \\
    --steps boxplot scatter_average anova ttests
```

The code and CLI command above loads three experiments (`Baseline`, `Model_1`, and `Model_2`),
executed all requested (via `--steps`, if supplied) statistical tests and data plot 
preparations, produces the requested plots and prints the ANOVA p‑value, and writes the CSVs.