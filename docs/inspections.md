# Inspection configuration

Each consignment is inspected according to the rules under the `inspection` configuration key.
Optionally, inspection of some consignments can be skipped using a release programs.

## Skipping inspections

Inspections can be skipped using release programs specified under the key `release_programs`.

Two programs are supported: a naive variation of the Cut Flower Release Program
and a full version of the _Cut Flower Release Program_.

Only one program can be specified at a time.

### Fixed Skip Lot Program

List of compliance levels and their associated ratios of inspected consignments:

```yaml
release_programs:
  fixed_skip_lot:
    levels:
      - name: 1
        sampling_fraction: 1
      - name: 2
        sampling_fraction: 0.5
      - name: 3
        sampling_fraction: 0
```

List of consignment properties (attributes) which determine into
which compliance level a consignment belongs to:

```yaml
    track:
      - origin
      - commodity
```

List which assigns values of tracked consignment properties to compliance levels:

```yaml
    consignment_records:
      - origin: Netherlands
        commodity: Hyacinthus
        compliance_level: 2
      - origin: Mexico
        commodity: Gerbera
        compliance_level: 3
```

Default compliance level when a consignment does not have a compliance level defined:

```yaml
    default_level: 1
```

### Dynamic Skip Lot Program

In the dynamic skip lot program, consignment dynamically fall to compliance
levels based on inspection results. The proportion of inspected consignments for
the same combination of consignment properties dynamically changes based on
previous simulation steps. The program is identified by the key
`dynamic_skip_lot`. An optional name can be added and will appear in the output.

```yaml
release_programs:
  dynamic_skip_lot:
    name: Dynamic Skip Lot
```

Inspection results are tracked for consignments grouped based on tracked
consignment properties specified as a list with `track`.

```yaml
track:
  - origin
  - commodity
```

Each group is assigned a level that determines the frequency of inspections.
Each compliance level has an associated fraction of consignments to be inspected
(`sampling_fraction`). The `name` key for a level is optional.

```yaml
levels:
  - name: Compliance Level 1
    sampling_fraction: 1
  - name: Compliance Level 2
    sampling_fraction: 0.5
  - name: Compliance Level 3
    sampling_fraction: 0.25
  - name: Compliance Level 4
    sampling_fraction: 0.1
```

The order of the levels is important, as groups move through the levels from the
first one in the list to the last one in the list. All groups start at the first
level or a custom start level specified with `start_level`, which can refer to
the level either by name or by a one-based index. The default start level is 1.

```yaml
start_level: Compliance Level 1
```

To advance to a higher level, a group must reach a certain number of consecutive
successful inspections, called the clearance number.

```yaml
clearance_number: 10
```

The tracking for the clearance number is reset after a group moves up a level.
If a consignment fails an inspection, the level for the group it belongs to is
reset to the start level. The consignment group can then move up the levels in
the standard manner. The groups can quickly move back to the previous level
if quick restating of the original level is enabled with `quick_restating`.

```yaml
quick_restating: true
```

While the default clearance number is used for restating by default, an
additional lower clearance number for restating can be specified with
`quick_restate_clearance_number`. If `quick_restate_clearance_number` is
provided, quick restating is automatically enabled even if `quick_restating` is
not provided.

```yaml
quick_restate_clearance_number: 5
```

### Naive Cut Flower Release Program

A prototype implementation of a simple theoretical release program
modeled after the Cut Flower Release Program (CFRP) is included in the
simulation as _Naive Cut Flower Release Program_ (`naive_cfrp`). When
activated, only one kind of flowers is inspected each day (a day is
based on the date which is a attribute of the consignment). The program
is applied to consignments which have flowers specified in `flowers` and
which have less then `max_boxes`. The program parameters can be
specified like this:

```yaml
release_programs:
  naive_cfrp:
    flowers:
      - Hyacinthus
      - Gerbera
      - Rosa
      - Actinidia
    max_boxes: 10  # do not apply to consignments larger than
```

### Cut Flower Release Program

_Main article: [Cut Flower Release Program](cfrp.md)_

A full _Cut Flower Release Program_ (`cfrp`) is included in the simulation
and is driven primarily by a schedule which determines qualifying flowers
(or generally, commodities) and _Flower of the Day_ (FotD), a flower to inspect
on a given day. A minimal configuration looks like this:

```yaml
release_programs:
  cfrp:
    schedule:
      file_name: schedule.csv
```

## Inspection unit

The inspection unit can be determined by:

```yaml
inspection:
  unit: items
```

The inspection unit can be either `items` for computing sample size
based on number of items in the consignment or `boxes` for computing
sample size based on number of boxes in the consignment.

## Partial box inspections

The proportion of items within a box to be inspected can be determined
by:

```yaml
inspection:
  within_box_proportion: 1
```

The value of `within_box_proportion` can be set to any value greater
than 0 and less than or equal to 1. By default, `within_box_proportion = 1`
meaning all items within a box can be inspected. If `within_box_proportion < 1`,
only the first `n = within_box_proportion * items_per_box` items in each box
will be inspected.

## Tolerance level

The contamination tolerance level can be determined by:

```yaml
inspection:
  tolerance_level: 0
```

The simulation provides a count of the number of missed consignments with
contamination rates below the specified `tolerance_level`, which can be
any value between 0 and 1. The resulting count can be used to adjust the
number of missed contaminated consignments when evaluating inspection
efficacy. For example, if an inspection strategy fails to detect 100 out
of 500 contaminated consignments (20% slippage), but 80 of the missed
consignments had a `contamination_rate` < `tolerance_level`, you may
choose to adjust the inspection slippage rate to only include the 20
consignments with contamination rates above the tolerance level
(decreases to 4% slippage).

## Sample strategy

The sample strategy can be determined by:

```yaml
inspection:
  sample_strategy: proportion
```

The sample strategy defines the method used to compute the number of
units to inspect. The possible sample strategies include `proportion`
for sampling a specified proportion of units, `hypergeometric` for
sampling to detect a specified contamination level at a specified
confidence level using the hypergeometric distribution, `fixed_n` for
sampling a specified number of units, and `all` for sampling all units.

### Proportion strategy

The settings for `proportion` are:

```yaml
inspection:
  proportion:
    value: 0.02
    min_boxes: 1
```

The proportion value is set by `proportion` and the minimum number of
boxes to be inspected is set by `min_boxes`. If `unit = "items"`, the
number of items to inspect is computed by `proportion * num_items`.
Similarly, if `unit = "boxes"`, the number of boxes to inspect is
computed by `proportion * num_boxes`.

### Hypergeometric strategy

The settings for `hypergeometric` are:

```yaml
inspection:
  hypergeometric:
    detection_level: 0.05
    confidence_level: 0.95
    min_boxes: 1
```

The minimum contamination level to be detected with sample is set by
`detection_level` at the confidence level set by `confidence_level`. The
minimum number of boxes to be inspected is set by `min_boxes`. The
sample size is calculated using a hypergeometric distribution (sampling
without replacement) as described in (Fosgate, 2009). The equation used
to compute the sample size is:

```math
n=(1-(alpha)^1/D*N)(N-(D*N-1/2))
```

where alpha is 1 - `confidence_level`, D is `detection_level`, and N is
`num_units`.

### Fixed _n_ strategy

The settings for `fixed_n` are:

```yaml
inspection:
  fixed_n: 10
```

The number of units to be inspected can be any integer set by `fixed_n`. If
`unit = "items"`, the sample size will be set to the minimum of two values:
`fixed_n` and the maximum number of inspectable items based on
`within_box_proportion` (`max_items = within_box_proportion * items_per_box * num_boxes`).
If `unit = "boxes"`, the sample size will be set to `fixed_n` if
`min_boxes <= fixed_n <= num_boxes`. If `fixed_n` is less than the minimum
number of boxes to inspect, number of boxes to inspect will be set to
`min_boxes`. If `fixed_n` exceeds the number of boxes in the consignment, number
of boxes to inspect will be set to `num_boxes`.

## Selection strategy

The unit selection strategy can be determined by:

```yaml
inspection:
  selection_strategy: random
```

While the sample strategy determines _how many_ units to inspect, the
selection strategy is used to determine _which_ units to select for
inspection. The possible selection strategies include `random` for
selecting units to inspect using a uniform random distribution,
`convenience` for selecting the first `n` units to inspect, or `cluster`
for selecting boxes for partial inspection. The `cluster` selection
strategy is valid only for the `item` inspection unit.

### Cluster strategy

The cluster selection strategy is used when `inspection_unit="item"` to
divide the sample size into clusters that can be selected from boxes
chosen either randomly (`cluster_selection="random"`) or at a systematic
interval (`cluster_selection="interval"`). This selection strategy
cannot be used with the highest inspection unit (e.g., `unit = "boxes"`).

The settings for `cluster` are:

```yaml
inspection:
  within_box_proportion: 0.1
  cluster:
    cluster_selection: random
    interval: 3
```

The method for selecting the cluster units (boxes in this case) is set
by `cluster_selection`. The possible values for `cluster_selection` are
`random` for selecting the cluster units using a random uniform
distribution and `interval` for selecting every _nth_ cluster unit. If
`cluster_selection="interval"`, the interval size is set by `interval`.
The proportion of items to inspect within each cluster unit is set by
`within_box_proportion`.

A simple example using the following configuration:

```yaml
consignment:
  items_per_box:
    default: 200
inspection:
  unit: item
  within_box_proportion: 0.25
  sample_strategy: hypergeometric
  selection_strategy: cluster
  cluster:
    cluster_selection: random
```

In this case, the sample size is calculated using the hypergeometric
approach based on the total number of items in the consignment and the
items to be inspected are selected using the cluster approach.

Let's say the computed sample size (`n_units_to_inspect`) is 200 items. The
following steps are used to determine which items to inspect. First, the
`within_box_proportion` value is used to determine how many clusters (i.e.,
boxes) are needed to get to the sample size. The number of items inspected per
box is `within_box_proportion * items_per_box` (`200 * 0.25 = 50`), so only 50
items would be inspected per box. The number of boxes that need to be opened to
get to the sample size is `n_units_to_inspect / inspect_per_box`
(`200 / 50 = 4`), so 4 boxes need to be opened. Once the number of boxes needed
is determined, those boxes are then selected from the consignment randomly since
`cluster_unit = "random"` and the first 25% of items are inspected convenience
style, i.e., first _n_ or tailgate.

The cluster selection strategy could be useful when using the
hypergeometric sample strategy with items as the inspection unit. An
important assumption for the hypergeometric sample size to work
effectively is that every unit has an equal chance of being selected.
This is feasible when using boxes as the inspection unit, since boxes
could be numbered and the inspector could be directed to select boxes
based on randomly generated box numbers. When using items as the sample
unit, however, ensuring every item has an equal chance of being selected
is more difficult, as there are likely too many items to individually
number and the items may be packaged in bunches and stacked within a
box. The cluster selection method does not ensure each item has an equal
chance of being selected, but it provides a sort of compromise to spread
the sample out across the consignment while still limiting the number of
boxes opened and items inspected.

## End strategy

Each simulation automatically runs two options for determining when to
end an inspection (end strategies). The two possible end strategies are
`to detection` and `to completion`.

For the `to detection` end strategy, the inspection ends as soon as a
contaminant is detected. For the `to completion` strategy, the
inspection continues until the full sample has been inspected,
regardless of contaminant detection.

The number of contaminated units detected for each end strategy is
compared to quantify the proportion of contaminants reported when the
inspection is ended at detection.

---

Next: [Run simulations](run.md)
