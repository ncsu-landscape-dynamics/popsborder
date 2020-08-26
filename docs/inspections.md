# Inspection configuration

## Inspection unit
The inspection unit can be determined by:

```
inspection:
  unit: stems
```

The inspection unit can be either `stems` for computing sample size based on 
number of stems in the shipment or `boxes` for computing sample size based on number of boxes in the shipment.

## Proportion of box to inspect
The proportion of stems within a box to be inspected can be determined by:

```
inspection:
  within_box_pct: 100
```

The value of `within_box_pct` can be set to any integer. By default, 100 
percent of stems within a box will be inspected. If `within_box_pct < 100`, the
 first `n = within_box_pct * stems_per_box` stems in each box will be inspected.

## Sample strategy
The sample strategy can be determined by:

```
inspection:
    sample_strategy: percentage
```

The sample strategy defines the method used to compute the number of units to inspect. The possible sample strategies include `percentage` for sampling a specified percent of units, `hypergeometric` for sampling to detect a specified infestation level at a specified confidence level using the hypergeometric distribution, `fixed_n` for sampling a specified number of units, and `all` for sampling all units.

### Percentage strategy

The settings for `percentage` are:

```
inspection:
    percentage:
        proportion: 0.02
        min_boxes: 1
```

The percentage value is set by `proportion` and the minimum number of boxes to
 be inspected is set by `min_boxes`. If `unit = "stems"`, the number of stems to inspect
 is computed by `proportion * num_stems`. Similarly, If `unit = "boxes"`, the number of boxes to inspect is computed by `proportion * num_boxes`.

### Hypergeometric strategy

The settings for `hypergeometric` are:

```
inspection:
    hypergeometric:
        detection_level: 0.05
        confidence_level: 0.95
        min_boxes: 1
``` 

The minimum infestation level to be detected with sample is set by `detection_level` 
at the confidence level set by `confidence_level`. The minimum number of boxes to be 
inspected is set by `min_boxes`. The sample size is calculated using a hypergeometric
distribution (sampling without replacement) as described in (Fosgate, 2009).
The equation used to compute the sample size is:
  
```math
n=(1-(alpha)^1/D)(N-(D-1/2))
```

### Fixed n strategy
The settings for `fixed_n` are:

```
inspection:
    fixed_n: 10
```

The number of units to be inspected can be any integer set by `fixed_n`. If `unit = "stems"`, the sample size will be set to the minimum of two values: `fixed_n` and the maximum number of inspectable stems based on within_box_pct (`max_stems = within_box_pct * stems_per_box * num_boxes`). If `unit = "boxes"`, the sample size will be set to `fixed_n` if `min_boxes <= fixed_n <= num_boxes`. If `fixed_n` is less than the minimum number of boxes to inspect, number of boxes to inspect will be set to `min_boxes`. If `fixed_n` exceeds the number of boxes in the shipment, number of boxes to inspect will be set to `num_boxes`.

## Selection strategy
The unit selection strategy can be determined by:

```
inspection:
    selection_strategy: random
```

While the sample strategy determines *how many* units to inspect, the selection strategy is used to determine *which* units to select for inspection. The possible selection strategies include `random` for selecting units to inspect
using a uniform random distribution, `tailgate` for selecting the first `n` 
units to inspect, or `hierarchical` for selecting boxes for partial inspection. The `hierarchical` selection strategy is only valid for the `stem` inspection unit.

Each simulation runs automatically two options in regard to determining
the end of an inspection. The two possible end strategies are
to first detection of pest
when an inspection ends as soon as a pest is detected and
to completion strategy when the inspection continues until the whole
sample was completed regardless of pest detection.
The number of infested units detected is compared to the actual number
of pests in sample to quantify number of reported pests for each strategy.

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

Tailgate with *n* boxes:

```
inspection:
  first_n_boxes: 2
```

---

Next: [Outputs](outputs.md)
