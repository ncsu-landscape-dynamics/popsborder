# Pest configuration

The pest arrangement within the shipment can be determined by:

```
pest:
  arrangement: random
```

The arrangement can be `random` for uniform random distribution,
`clustered` for one or more pest clusters within stems of the shipment,
and `random_box` for one or more random boxes having pest.

For arrangement `random` and `clustered`, the infestation rate can be
determined by:

```
pest:
  infestation_rate:
    distribution: beta
    parameters:
    - 4
    - 60
```

The infestation rate can be also set using a fixed value (rather than
random values based on the given distribution):

```
pest:
  infestation_rate:
    distribution: fixed_value
    value: 0.05
```

The `random` arrangement does not have any further configuration besides
`infestation_rate`.

The settings for `clustered` is:

```
  clustered:
    max_stems_per_cluster: 10
    distribution: gamma
    parameters:
    - 4
    - 2
```

The cluster size in terms of number of stems is limited by
`max_stems_per_cluster`. If `max_stems_per_cluster` is exceeded, more
than one cluster is generated so that number of stems in each cluster
conforms to this limit.

The distribution for clustered can be `gamma`, `random`, and `continuous`
and it drives the placement of infested stems within a cluster.
The `gamma` option uses the gamma distribution and takes two parameters.
The `random` option uses the uniform random distribution. The cluster
width is defined by the first and only parameter of this distribution.
The `continuous` distribution does not have any parameters and produces
infested stems next to each other so the number of infested stems in the
cluster is the same as the width of the cluster.

The settings for `random_box` is:

```
pest:
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

Probability of shipment being infested is driven by `probability`
while the number of boxes infested within a shipment is driven by `ratio`.
The infestation within one box is determined by `in_box_arrangement`
which can have values `all`, `first`, `one_random`, and `random`.
For `all`, all stems within a box are infested.
With `first`, only the first stem in the box will get pest.
`one_random` is similar to `first`, but a random stem is picked to get
pest.
The `random` in-box arrangement will place pests in a box using uniform
random distribution. The number of pests to be placed is determined
using the distribution configured using the `infestation_rate` key
which takes meaning *infestation rate within a box* instead of its usual
meaning *infestation rate within a shipment*.
In that case, the configuration may look like this:

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
