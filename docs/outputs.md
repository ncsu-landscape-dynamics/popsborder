# Outputs

## Stem and box pretty printing

Pretty printing of individual shipments and stems can be enabled by
`--pretty` in the command line with output like this:

```
━━ Shipment ━━ Boxes: 3 ━━ Stems: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛 ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛 | ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Shipment ━━ Boxes: 2 ━━ Stems: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ | ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Th above is the default output (equivalent with `--pretty=boxes`).
Separation of individual boxes can be disabled using `--pretty=stems`
where the only unit shown graphically are the stems. Possible output
looks like this:

```
━━ Shipment ━━ Boxes: 3 ━━ Stems: 30 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🐛 ✿ ✿ 🐛 ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
━━ Shipment ━━ Boxes: 2 ━━ Stems: 20 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ ✿ 🐛
```

Finally, option `--pretty=boxes_only` focuses just on the boxes and does
not show individual stems:

```
── Shipment ── Boxes: 6 ── Stems: 60 ───────────────────────────────────
🐛 🐛 ✿ ✿ ✿ 🐛
── Shipment ── Boxes: 4 ── Stems: 40 ───────────────────────────────────
✿ ✿ ✿ 🐛
```

This can be further configured using `pretty` key in the configuration
file:

```
pretty:
  flower: o
  bug: x
  horizontal_line: "-"
  box_line: "|"
  spaces: false
```

Configuration like the above can allow you to use `--pretty` even when
Unicode characters are properly displayed in your terminal. Note that
some characters, such as the dash (`-`) above, need to be in quotes
because they have a special meaning in YAML.

The output with the settings above will look like:

```
-- Shipment -- Boxes: 4 -- Stems: 40 -----------------------------------
xooooooooo|ooooooxooo|oooooooooo|xoooooooox
-- Shipment -- Boxes: 6 -- Stems: 60 -----------------------------------
xxooooooxx|oooooooooo|oooxooooxx|ooooooooxo|ooooxooooo|ooooxoooox
```
