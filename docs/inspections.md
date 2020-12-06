# Inspection configuration

## Inspection unit
The inspection unit can be determined by:

```
inspection:
  unit: stems
```

The inspection unit can be either `stems` for computing sample size
based on number of stems in the shipment or `boxes` for computing sample
size based on number of boxes in the shipment.

## Partial box inspections
The proportion of stems within a box to be inspected can be determined
by:

```
inspection:
  within_box_proportion: 1
```

The value of `within_box_proportion` can be set to any value greater
than 0 and less than or equal to 1. By default, `within_box_proportion =
1` meaning all stems within a box can be inspected. If
`within_box_proportion < 1`, only the first `n = within_box_proportion *
stems_per_box` stems in each box will be inspected.

## Sample strategy
The sample strategy can be determined by:

```
inspection:
  sample_strategy: proportion
```

The sample strategy defines the method used to compute the number of
units to inspect. The possible sample strategies include `proportion`
for sampling a specified proportion of units, `hypergeometric` for sampling
to detect a specified infestation level at a specified confidence level
using the hypergeometric distribution, `fixed_n` for sampling a
specified number of units, and `all` for sampling all units.

### Proportion strategy

The settings for `proportion` are:

```
inspection:
  proportion:
      value: 0.02
      min_boxes: 1
```

The proportion value is set by `proportion` and the minimum number of
 boxes to be inspected is set by `min_boxes`. If `unit = "stems"`, the
 number of stems to inspect is computed by `proportion * num_stems`.
 Similarly, if `unit = "boxes"`, the number of boxes to inspect is
 computed by `proportion * num_boxes`.

### Hypergeometric strategy

The settings for `hypergeometric` are:

```
inspection:
  hypergeometric:
      detection_level: 0.05
      confidence_level: 0.95
      min_boxes: 1
``` 

The minimum infestation level to be detected with sample is set by
`detection_level` at the confidence level set by `confidence_level`. The
minimum number of boxes to be inspected is set by `min_boxes`. The
sample size is calculated using a hypergeometric distribution (sampling
without replacement) as described in (Fosgate, 2009). The equation used
to compute the sample size is:
  
```math
n=(1-(alpha)^1/D)(N-(D-1/2))
```

### Fixed *n* strategy
The settings for `fixed_n` are:

```
inspection:
  fixed_n: 10
```

The number of units to be inspected can be any integer set by `fixed_n`.
If `unit = "stems"`, the sample size will be set to the minimum of two
values: `fixed_n` and the maximum number of inspectable stems based on
`within_box_proportion` (`max_stems = within_box_proportion *
stems_per_box * num_boxes`). If `unit = "boxes"`, the sample size will
be set to `fixed_n` if `min_boxes <= fixed_n <= num_boxes`. If `fixed_n`
is less than the minimum number of boxes to inspect, number of boxes to
inspect will be set to `min_boxes`. If `fixed_n` exceeds the number of
boxes in the shipment, number of boxes to inspect will be set to
`num_boxes`.

## Selection strategy
The unit selection strategy can be determined by:

```
inspection:
  selection_strategy: random
```

While the sample strategy determines *how many* units to inspect, the
selection strategy is used to determine *which* units to select for
inspection. The possible selection strategies include `random` for
selecting units to inspect using a uniform random distribution,
`tailgate` for selecting the first `n` units to inspect, or
`hierarchical` for selecting boxes for partial inspection. The
`hierarchical` selection strategy is valid only for the `stem`
inspection unit.

### Hierarchical stratgey
The term hierarchical is meant to describe that the sample size is
computed based on a lower unit (stems), but the sample selection uses
the higher unit (boxes). This selection strategy cannot be used with the
highest inspection unit (e.g., `unit = "boxes"`).

The settings for `hierarchical` are:

``` 
inspection:
  hierarchical: 
    outer: random
    interval: 3 
```

The method for selecting the outer units (boxes in this case) is set by
`outer`. The possible values for `outer` are `random` for selecting the
outer units using a random uniform distribution and `interval` for
selecting every *nth* outer unit. If `outer = "interval"`, the interval
size is set by `interval`.

A simple example using the following configuration: ``` shipment:
stems_per_box: default: 200 inspection: unit: stem
within_box_proportion: 0.25 sample_strategy: hypergeometric
selection_strategy: hierarchical hierarchical: outer: random ```

In this case, the sample size is calculated using the hypergeometric
approach based on the total number of stems in the shipment and the
stems to be inspected are selected using the hierarchical approach.

Let's say the computed sample size (`n_units_to_inspect`) is 200 stems.
The following steps are used to determine which stems to inspect. First,
the `within_box_proportion` value is used to determine how many boxes
need to be opened to get to the sample size. The number of stems
inspected per box is `within_box_proportion` * `stems_per_box` (200 *
0.25 = 50), so only 50 stems would be inspected per box. The number of
boxes that need to be opened to get to the sample size is
`n_units_to_inspect` / `inspect_per_box` (200 / 50 = 4), so 4 boxes need
to be opened. Once the number of boxes needed is determined, those boxes
are then selected from the shipment randomly since `outer = "random"`
and the first 25% of stems are inspected tailgate style, i.e., first
*n*. 

The hierarchical selection strategy was designed for use with
hypergeometric sample size computation using stems as the inspection
unit. An important assumption for the hypergeometric sample size to work
effectively is that every unit has an equal chance of being selected.
This is feasible when using boxes as the inspection unit, since boxes
could be numbered and the inspector could be directed to select boxes
based on randomly generated box numbers. When using stems as the sample
unit, however, ensuring every stem has an equal chance of being selected
is more difficult, as there are likely too many stems to individually
number and the stems may be packaged in bunches and stacked within a
box. The hierarchical selection method does not ensure each stem has an
equal chance of being selected, but it provides a sort of compromise to
spread the sample out across the shipment while still limiting the
number of boxes opened and stems inspected.

## End strategy
Each simulation automatically runs two options for determining when to
end an inspection (end strategies). The two possible end strategies are
`to detection` and `to completion`.

For the `to detection` end strategy, the inspection ends as soon as a
pest is detected. For the `to completion` strategy, the inspection
continues until the full sample has been inspected, regardless of pest
detection.

The number of infested units detected for each end strategy is compared
to quantify the proportion of pests reported when the inspection is
ended at detection. 

## Cut Flower Release Program (CFRP)

```
release_programs:
  naive_cfrp:
    flowers:
    - Hyacinthus
    - Gerbera
    - Rosa
    - Actinidia
    max_boxes: 10  # do not apply to shipments larger than
```

---

Next: [Outputs](outputs.md)
