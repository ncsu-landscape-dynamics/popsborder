# Contaminant configuration

## Contamination unit
The unit used for contaminating a consignment can be determined by:
```
contamination:
  contamination_unit: items
```

The possible values for `contamination_unit` include `items` and `boxes`. If
`contamination_unit` = items, the contamination rate (described below) is applied to
the total number of items in the consignment and individual items are contaminated
using the specified contaminant arrangement method (described below). 

Alternatively, if `contamination_unit` = boxes, the contamination rate is
applied to the total number of boxes in the consignment. The number of boxes to
contaminate is computed as a decimal (float). Full boxes are contaminated (all
items within box), except for the last box which uses the remainder of the
computed number of boxes to contaminate to determine the number of items to
contaminate within the box. Items are contaminated in a continuous arrangement
(sequentially). For example, if there are 10 boxes with 200 items per box and
the contamination rate is 0.15, the number of boxes to contaminate is 1.5. One
full box and the first half of one box will be contaminated.

## Contamination rate
The contamination rate can be determined by:
```
contamination:
  contamination_rate:
    distribution: beta
    parameters:
    - 4
    - 60
```
The possible values for `distribution` include `beta` and `fixed_value`.

If `distribution` = `beta`, a beta probability distribution of contamination rates
is used to draw a random contamination rate for every consignment. If using the beta
distribution, two shape parameter values are required to define the desired beta
distribution of contamination rates. An contamination rate mean and standard
deviation can be used to determine the beta distribution shape parameters if
desired using this calculator: https://www.desmos.com/calculator/kx83qio7yl.

If `distribution` = `fixed_value`, a constant contamination rate is used for every
consignment (rather than a random value based on a beta distribution). When using a
fixed value, the desired value must specified as follows:

```
contamination:
  contamination_rate:
    distribution: fixed_value
    value: 0.05
```

## Contaminant arrangement
The contaminant arrangement within the consignment can be determined by:

```
contamination:
  arrangement: random
```

The `arrangement` can be `random` for uniform random distribution, `clustered`
for one or more contaminant clusters within items of the consignment, and `random_box` for
one or more random boxes being contaminated.

### Random arrangement
The `random` arrangement does not have any further configuration. The computed
number of items or boxes (based on the contamination rate described above) are
uniform randomly selected from the total number of units and contaminated.

### Clustered arrangement
If using `arrangement` = `clustered`, the configuration is as follows:

```
  clustered:
    contaminated_units_per_cluster: 200
```

The number of contaminated units (items or boxes depending on
`contamination_unit`) within a cluster is limited by
`contaminated_units_per_cluster`. If `contaminated_units_per_cluster` is
exceeded, more than one cluster is generated so that the number of contaminated
units in each cluster conforms to this limit.

If `contamination_unit` = `boxes`, no additional parameters are used.

If `contamination_unit` = `items`, a `distribution` should also be specified.
The configuration is as follows:

```
  clustered:
    contaminated_units_per_cluster: 200
    distribution: random
      cluster_item_width: 600
```

Items can be placed into clusters using a `random` or `continuous` distribution.

The `continuous` distribution places contaminated items within each cluster
continuously (next to each other) so the number of contaminated items in the
cluster is always the same as the total width of the cluster. The parameter
`cluster_item_width` is not used if the cluster distribution is `continuous`.

The `random` distribution option places contaminated items within each cluster
using a uniform random distribution. The total width of the cluster (range over
which items may be contaminated) is limited by `cluster_item_width` and has the
effect of increasing or decreasing the density of contaminated items within a
cluster. The density of contaminated items within a cluster must be sufficiently
high to achieve the contamination rate. To avoid overlapping clusters, the items
are divided into strata large enough for one cluster and strata to contaminate
are selected uniform randomly.

### Random box
The settings for `random_box` is:

```
contamination:
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

Probability of consignment being contaminated is driven by `probability` while the
number of boxes contaminated within a consignment is driven by `ratio`. The contamination
within one box is determined by `in_box_arrangement` which can have values
`all`, `first`, `one_random`, and `random`. For `all`, all items within a box
are contaminated. With `first`, only the first item in the box will be contaminated.
`one_random` is similar to `first`, but a random item is selected for contamination. The
`random` in-box arrangement will place contaminants in a box using uniform random
distribution. The number of contaminants to be placed is determined using the
distribution configured using the `contamination_rate` key which takes meaning
*contamination rate within a box* instead of its usual meaning *contamination rate
within a consignment*. In that case, the configuration may look like this:

```
contamination:
  contamination_rate:
    distribution: beta
    parameters: [20, 30]
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

---

Next: [Inspections](inspections.md)
