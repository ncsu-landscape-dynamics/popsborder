# Contaminant configuration

## Contamination unit

The unit used for contaminating a consignment can be determined by:

```yaml
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

```yaml
contamination:
  contamination_rate:
    distribution: beta
    parameters:
      - 4
      - 60
```

The distribution parameters can also be specified as a mapping (dictionary) with
`a` being the first parameter and `b` the second:

```yaml
contamination:
  contamination_rate:
    distribution: beta
    parameters:
      a: 4
      b: 60
```

In tabular configuration, the above looks like:

| Parameter key                                 | Value |
| --------------------------------------------- | ----- |
| contamination/contamination_rate/distribution | beta  |
| contamination/contamination_rate/parameters/a | 4     |
| contamination/contamination_rate/parameters/b | 60    |

The possible values for `distribution` include `beta` and `fixed_value`.

If `distribution` = `beta`, a beta probability distribution of contamination rates
is used to draw a random contamination rate for every consignment. If using the beta
distribution, two shape parameter values are required to define the desired beta
distribution of contamination rates. An contamination rate mean and standard
deviation can be used to determine the beta distribution shape parameters if
desired using this calculator: <https://www.desmos.com/calculator/kx83qio7yl>.

If `distribution` = `fixed_value`, a constant contamination rate is used for every
consignment (rather than a random value based on a beta distribution). When using a
fixed value, the desired value must specified as follows:

```yaml
contamination:
  contamination_rate:
    distribution: fixed_value
    value: 0.05
```

## Contaminant arrangement

The contaminant arrangement within the consignment can be determined by:

```yaml
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

```yaml
contamination:
  arrangement: clustered
```

#### Single-parameter clustering

With cluster `distribution` set to `single`, the items that can be contaminated
are limited to a subset of the items. The size of the subset is determined by
a single clustering value, which is an inverse proportion. A higher value
results in a lower proportion (smaller subset) of the consignment being
available for contamination and a more pronounced, denser infestation cluster.
A clustering value of zero results in all items being available for
contamination and a uniform random distribution of contaminated items across
the whole consignment. The number of contaminated items within the cluster
subset is determined by the contamination rate. The total number of
contaminated items does not depend on the clustering value.

```yaml
clustered:
  distribution: single
  value: 0.9
```

Note that a cluster that partially extends beyond the end of the consignment is
split, and the part that extends beyond the end of the consignment is placed at
the beginning of the consignment, as if the (one-dimensional) consignment was
circular.

Whole configuration of contamination may then look like this:

```yaml
contamination:
  contamination_rate:
    distribution: fixed_value
    value: 0.3
  contamination_unit: item
  arrangement: clustered
  clustered:
    distribution: single
    value: 0.9
```

#### Multi-parameter clustering

Multi-parameter clustering uses several parameters to create the clusters,
starting with number of contaminated units per cluster:

```yaml
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

```yaml
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

```yaml
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
_contamination rate within a box_ instead of its usual meaning _contamination rate
within a consignment_. In that case, the configuration may look like this:

```yaml
contamination:
  contamination_rate:
    distribution: beta
    parameters: [20, 30]
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

## Consignment-specific contamination

Contamination configuration can be different for different consignments.
A key called `consignments` under `contamination` determines what consignments
should be contaminated. If the key is present, only the consignments matching
the specified rules are contaminated. If the key is not present, all
consignments are contaminated and the same contamination settings is applied to all.

### Rules for applying contamination

Consignments which should be contaminated need to match the rules specified under
`consignments` which is a list of rules. For example, to contaminate only Rose,
the `commodity` key can be specified:

```yaml
contamination:
  consignments:
    - commodity: Rose
```

Multiple commodities can be specified:

```yaml
contamination:
  consignments:
    - commodity: Rose
    - commodity: Sedum
    - commodity: Tulipa
```

In this case, consignments which contain Rose, Sedum, and Tulipa will be contaminated.

The consignments can be selected by `commodity`, `origin`, and `port`. All of the specified values
need to match. For example, to contaminate only Rose from Colombia coming to FL Miami Air CBP,
we can write:

```yaml
contamination:
  consignments:
    - commodity: Rose
      origin: Colombia
      port: FL Miami Air CBP
```

Although any combination is accepted as valid input, specifying overlapping rules may result in
unexpected behavior. For example, in case you specify only `commodity` in one rule and `port`
in another rule, it is hard to tell which rule is applied to which consignment. This is an issue
when it is used in combination with different contamination settings for different consignments
(see below).

Contamination can also be limited to certain time period. For example, here we specify that Tulipa
coming between September 29th, 2022 and November 15th, 2022 should be contaminated:

```yaml
contamination:
  consignments:
    - commodity: Tulipa
      start_date: 2022-09-29
      end_date: 2022-10-15
```

If only `start_date` is specified, all matching consignments at and after that date are contaminated.
Similarly, `end_date` specifies last day when the consignments are contaminated even if no
`start_date` was specified.

### Setting consignment-specific parameters

When all selected consignments should use the same contamination configuration,
the `contamination` on the top-level is used, i.e., the contamination configuration is done
exactly as if it would apply to all consignment and it is rules under `consignments` which limit
to which consignment the contamination is applied.

```yaml
contamination:
  consignments:
    - commodity: Tulipa
    - commodity: Rose
      origin: Mexico
    - commodity: Sedum
  contamination_unit: item
  arrangement: random
```

However, each of the consignment rules can have its own contamination under the key
`contamination`, for example:

```yaml
contamination:
  consignments:
    - commodity: Tulipa
      contamination:
        arrangement: random_box
        contamination_unit: box
    - commodity: Rose
      origin: Mexico
      contamination:
        arrangement: random
        contamination_unit: box
```

This nested configuration can contain exactly the same as the top-level `contamination`
except for the `consignments` key.

If the nested `contamination` is present, the top-level `contamination` is ignored unless
`use_contamination_defaults` is set to `true`. If `use_contamination_defaults: true` is set,
then the top-level `contamination` is used to get default values which can be then optionally
overwritten by values from the nested `contamination`.

In the following example, both consignments with both Tulipa and Rose will be contaminated and
will use values from the top-level `contamination` and at the same time, these values will be
overwritten by the nested `contamination`. As a result, contamination configuration for Tulipa
will have `arrangement: random_box` and `contamination_unit: item`, while contamination
for Rose will have `arrangement: random` and `contamination_unit: box`.

```yaml
contamination:
  consignments:
    - commodity: Tulipa
      use_contamination_defaults: true
      contamination:
        arrangement: random_box
    - commodity: Rose
      use_contamination_defaults: true
      contamination:
        contamination_unit: box
  contamination_unit: item
  arrangement: random
```

In summary, there are three different scenarios of usage of the top-level `contamination`.
First, the top-level `contamination` is used implicitly when there is not nested `contamination`.
Second, the top-level `contamination` is not used at all when the nested `contamination` is provided.
And third, when the nested `contamination` is provided together with `use_contamination_defaults: true`,
the values top-level `contamination` are used for parameters not provided in the nested `contamination`.
The following example shows these three cases:

```yaml
contamination:
  consignments:
    - commodity: Sedum
    - commodity: Tulipa
      contamination:
        arrangement: random_box
        contamination_unit: box
    - commodity: Rose
      origin: Mexico
      use_contamination_defaults: true
      contamination:
        contamination_unit: box
  contamination_unit: item
  arrangement: random
```

---

Next: [Inspections](inspections.md)
