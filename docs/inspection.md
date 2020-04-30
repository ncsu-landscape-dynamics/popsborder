# Inspection configuration

The inspection unit can be determined by:

```
inspection:
  unit: stems
```

The inspection unit can be `stems` for computing sample size based on 
number of stems in the shipment or `boxes` for computing sample size 
based on number of boxes in the shipment.

The proportion of stems within a box to be inspected can be determined by:

```
inspection:
  within_box_pct: 100
```

The value of `within_box_pct` can be set to any integer. By default, 100 
percent of stems within a box will be inspected. If `within_box_pct < 100`, the
 first `n = within_box_pct * stems_per_box` stems in each box will be inspected.

The sample strategy can be determined by:

```
inspection:
    sample_strategy: percentage
```

The possible sample strategies include `percentage` for sampling a specified
 percent of units, `hypergeometric` for sampling to detect a specified infestation
  level, `fixed_n` for sampling a specified number of units, and `all` for
   sampling all units.

The settings for `percentage` are:

```
inspection:
    percentage:
        proportion: 0.02
        min_boxes: 1
```

The percentage of units is set by `proportion` and the minimum number of boxes to
 be inspected is set by `min_boxes`. If `unit = "stems"`, the number of stems to inspect
 is computed by `proportion * num_stems` and converted to number of boxes to inspect
  based on `stems_per_box * within_box_pct`.
  
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

The settings for `fixed_n` are:

```
inspection:
    fixed_n: 10
```

The number of units to be inspected can be any integer set by `fixed_n`. If the inspection 
`unit = "stems"`, `fixed_n` will be converted to number of boxes to inspect based on the
number of stems to be inspected per box. If the number of boxes to inspect exceed
the number of boxes in the shipment, number of boxes to inspect will be set to `num_boxes`.

The inspection unit selection strategy can be determined by:

```
inspection:
    selection_strategy: random
```

This setting is used to determine which units in the shipment to inspect. The possible 
selection strategies include `random` for selecting units to inspect
using a uniform random distribution or `tailgate` for selecting the first `n` 
units to inspect. The number of units to select is set by the sampling strategy functions.

The inspection end strategy can be determined by:

```
inspection:
    end_strategy: to_detection
```

This setting is used to determine when to end an inspection. The possible end strategies 
include `to_detection` for ending an inspection as soon as a pest is detected and `to_completion`
for inspecting all units in the sample regardless of pest detection. The number of infested
units detected is compared to the actual number of pests in sample to quantify number of 
reported pests for each strategy.

Cut Flower Release Program (CFRP):

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
