# Outputs

## Stem and box pretty printing

Pretty printing of individual shipments and stems can be enabled by `--pretty`
in the command line with output like this:

```
━━ Shipment ━━ Boxes: 3 ━━ Stems: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛 ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛 | ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Shipment ━━ Boxes: 2 ━━ Stems: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Th above is the default output (equivalent with `--pretty=boxes`). Separation of
individual boxes can be disabled using `--pretty=stems` where the only unit
shown graphically are the stems. Possible output looks like this:

```
━━ Shipment ━━ Boxes: 3 ━━ Stems: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Shipment ━━ Boxes: 2 ━━ Stems: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Finally, option `--pretty=boxes_only` focuses just on the boxes and does not
show individual stems:

```
── Shipment ── Boxes: 6 ── Stems: 60 ───────────────────────────────────
🐛 🐛 ✿ ✿ ✿ 🐛
── Shipment ── Boxes: 4 ── Stems: 40 ───────────────────────────────────
✿ ✿ ✿ 🐛
```

This can be further configured using `pretty` key in the configuration file:

```
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

```
-- Shipment -- Boxes: 4 -- Stems: 40 -----------------------------------
xooooooooo|ooooooxooo|oooooooooo|xoooooooox
-- Shipment -- Boxes: 6 -- Stems: 60 -----------------------------------
xxooooooxx|oooooooooo|oooxooooxx|ooooooooxo|ooooxooooo|ooooxoooox
```

## Output details of stems and indexes inspected

Alternatively, if you want to plot and further analyze the simulated shipments
and inspections, use `detailed=True` in the `run_scenarios()` function to
return an object with arrays of stems (binary values representing infested or
not) and the stem indexes inspected. If multiple simulation iterations
are being used, the details from the first simulation will be used.

```
num_shipments = 10
results, details = run_scenarios(
    config=config,
    scenario_table=scenario_table,
    seed=42,
    num_simulations=1,
    num_shipments=num_shipments,
    detailed=True,
)
```

See the `scenarios` documentation and the validation plots Jupyter notebook
(validation_plots.ipynb) for further details on how to use `run_scenarios()` and
the details object. The stems and inspected indexes are visualized in the
notebook to confirm that the shipment are being infested and inspected as
configured.

If using a command line interface to run the simulation, the flags `--detailed`
or `-d` can be used to print the details object in the terminal. However, using
the details object in the terminal is not recommended as it includes the stems
and indexes inspected for the entire simulation and may be very large.
