# Pest configuration

## Infestation unit
The unit used for infesting a shipment can be determined by:
```
pest:
  infestation_unit: stems
```

The possible values for `infestation_unit` include `stems` and `boxes`. If
`infestation_unit` = stems, the infestation rate (described below) is applied to
the total number of stems in the shipment and individual stems are infested
using the specified pest arrangement method (described below). Alternatively, if
`infestation_unit` = boxes, the infestation rate is applied to the total number
of boxes in the shipment and whole boxes are infested using the specified pest
arrangement method.

## Infestation rate
The infestation rate can be determined by:
```
pest:
  infestation_rate:
    distribution: beta
    parameters:
    - 4
    - 60
```
The possible values for `distribution` include `beta` and `fixed_value`.

If `distribution` = `beta`, a beta probability distribution of infestation rates
is used to draw a random infestation rate for every shipment. If using the beta
distribution, two shape parameter values are required to define the desired beta
distribution of infestation rates. An infestation rate mean and standard
deviation can be used to determine the beta distribution shape parameters if
desired using this calculator: https://www.desmos.com/calculator/kx83qio7yl.

If `distribution` = `fixed_value`, a constant infestation rate is used for every
shipment (rather than a random value based on a beta distribution). When using a
fixed value, the desired value must specified as follows:

```
pest:
  infestation_rate:
    distribution: fixed_value
    value: 0.05
```

## Pest arrangement
The pest arrangement within the shipment can be determined by:

```
pest:
  arrangement: random
```

The `arrangement` can be `random` for uniform random distribution, `clustered`
for one or more pest clusters within stems of the shipment, and `random_box` for
one or more random boxes having pest.

### Random arrangement
The `random` arrangement does not have any further configuration. The computed
number of stems or boxes (based on the infestation rate described above) are
uniform randomly selected from the total number of units and infested.

### Clustered arrangement
If using `arrangement` = `clustered`, the configuration is as follows:

```
  clustered:
    max_infested_stems_per_cluster: 10
    distribution: gamma
    parameters:
    - 4
    - 2
```

The cluster size in terms of infested stems is limited by
`max_infested_stems_per_cluster`. If `max_infested_stems_per_cluster` is
exceeded, more than one cluster is generated so that number of stems in each
cluster conforms to this limit. Note that `max_infested_stems_per_cluster` is
also used to determine infested boxes per cluster when `infestation_unit` =
`boxes` by dividing `max_infested_stems_per_cluster` by `stems_per_box`.

The distribution used to place infested stems within each cluster can be
`gamma`, `random`, or `continuous`. The `gamma` option uses the gamma
distribution and takes two parameters (shape and rate) that determine the total
width of the cluster (range over which stems may be randomly infested) and
probability distriubtion shape. The `random` option uses the uniform random
distribution and takes one parameter to define the total width of the cluster
(range over which stems may be randomly infested). Note that when
`infestation_unit` = `boxes`, the `random` arrangement does not use this total
width parameter. In this case, the total width of the cluster in terms of boxes
will equal `max_infested_stems_per_cluster` / `stems_per_box` rounded to nearest
integer. The `continuous` distribution does not have any parameters and produces
infested stems next to each other so the number of infested stems in the cluster
is always the same as the total width of the cluster.

### Random box
The settings for `random_box` is:

```
pest:
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

Probability of shipment being infested is driven by `probability` while the
number of boxes infested within a shipment is driven by `ratio`. The infestation
within one box is determined by `in_box_arrangement` which can have values
`all`, `first`, `one_random`, and `random`. For `all`, all stems within a box
are infested. With `first`, only the first stem in the box will get pest.
`one_random` is similar to `first`, but a random stem is picked to get pest. The
`random` in-box arrangement will place pests in a box using uniform random
distribution. The number of pests to be placed is determined using the
distribution configured using the `infestation_rate` key which takes meaning
*infestation rate within a box* instead of its usual meaning *infestation rate
within a shipment*. In that case, the configuration may look like this:

```
pest:
  infestation_rate:
    distribution: beta
    parameters: [20, 30]
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

---

Next: [Inspections](inspections.md)
