# Consignment configuration

The consignments can be either purely synthetic or based on AQAS inspection
 records (Form 280 or AQIM). Configuration for the consignments is under
 the `consignment` key in the configuration file.

## Synthetic consignments

The two main keys for configuration of the synthetic consignment generator
are `boxes` and `items_per_box`. The `min` and `max` values of `boxes`
determine the range of sizes of consignments within the simulation. The
`default` value of `items_per_box` determines how many items are in one
box. An example configuration with consignments with 10 to 100 boxes and
200 items per box, i.e., 2000 to 20,000 items per consignments follows.

```yaml
consignment:
  boxes:
    min: 10
    max: 100
  items_per_box:
    default: 200
```

Currently, no further settings for `items_per_box` is possible, but in
the future further settings might be added.

The generator adds origin, flower (commodity type), and port (where
consignment was received). These are randomly selected from the lists
specified in the configuration like so:

```yaml
  origins:
  - Netherlands
  - Mexico
  - Israel
  - Japan
  - New Zealand
  - India
  - Tanzania
  flowers:
  - Hyacinthus
  - Rosa
  - Gerbera
  - Agapanthus
  - Aegilops
  - Protea
  - Liatris
  - Mokara
  - Anemone
  - Actinidia
  ports:
  - NY JFK CBP
  - FL Miami Air CBP
  - HI Honolulu CBP
  - AZ Phoenix CBP
  - VA Dulles CBP
  - CA San Francisco CBP
  - WA Seattle Air CBP
  - TX Brownsville CBP
  - WA Blaine CBP
```

## F280-based consignments

Consignments in the simulation can be based on real F280 records. In that
case, a CSV file needs to be specified using the `f280_file` key.

The CSV is expected to have the following columns:
 * QUANTITY which will be used as number of items,
 * PATHWAY which is used to determine the `items_per_box` value (case
   insensitive),
 * REPORT_DT is used for date,
 * COMMODITY as the flower (commodity type),
 * ORIGIN_NM as origin, and
 * LOCATION as port (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text
fields (`"`). The path is absolute or relative to the place where the
Python program is running.


## AQIM-based consignments

Consignments in the simulation can also be based on AQIM inspection
records. In that case, a CSV file needs to be specified using the
`aqim_file` key.

The CSV is expected to have the following columns:
 * UNIT which is used to specify the unit (must be items or boxes) used
   in QUANTITY.
 * QUANTITY which is used as number of items or number of boxes
   depending on UNIT specified,
 * CARGO_FORM which is used to determine the `items_per_box` value
   similar to PATHWAY in F280 (case insensitive),
 * CALENDAR_YR is used for date (YYYY only),
 * COMMODITY_LIST is used as the flower (commodity type),
 * ORIGIN as origin, and
 * LOCATION as port of entry (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text
fields (`"`). The path is absolute or relative to the place where the
Python program is running.

## Items per box
To create the boxes (of items) for the simulation, a value for
`items_per_box` needs to be specified. F280 and AQIM inspections records
include information about the consignment pathway, which can be used to
vary the value of `items_per_box`. For example, the following is a
configuration for generating consignments using a file called
`AQIM_sample.csv` with `items_per_box` values that vary by `air` and
`maritime` pathways. If the consignment arrives via an air pathway, one box
will contain 50 items. If the consignment arrives via a maritime pathway,
one box will contain 500 items. If the pathway is not `air` or
`maritime`, a default value of 100 items per box is used.

```yaml
consignment:
  aqim_file: aqim_sample.csv
  items_per_box:
    default: 100
    air:
      default: 50
    maritime:
      default: 700
```

Notice that the values for `items_per_box` are under additional key
`default`. In the future, the simulation may support other keys for
specific commodities, origins, or ports.


---

Next: [Pests](contamination.md)
