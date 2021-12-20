# Consignment configuration

## Consignment generation method
The consignments can be either purely synthetic or based on inspection records
(e.g., Form 280 or AQIM). Configuration for the consignments is under the
`consignment` key in the configuration file.

The `generation_method` key can be either `parameter_based` to generate
synthetic consignments based on user-provided list of parameter values, or
`input_file` to create consignments that match inspection records in a CSV
file.

```yaml
consignment:
  generation_method: parameter_based
```

## Items per box

To create the boxes (of items) for each consignment, a value for `items_per_box`
needs to be specified. 

```yaml
consignment:
  items_per_box:
    default: 200
```

Only the `default` value for `items_per_box` is required, but the user may also
vary the value by transport pathway. For example, F280 and AQIM inspections
records include information about the consignment pathway, which can be used to
vary the value of `items_per_box`. The following is a configuration for
generating consignments using a file called `AQIM_sample.csv` with
`items_per_box` values that vary by `air` and `maritime` pathways. If the
consignment arrives via an air pathway, one box will contain 200 items. If the
consignment arrives via a maritime pathway, one box will contain 700 items. If
the pathway is not `air` or `maritime`, a default value of 100 items per box is
used.

```yaml
consignment:
  generation_method: input_file
  items_per_box:
    default: 100
    air:
      default: 200
    maritime:
      default: 700
  input_file:
    file_type: AQIM
    file_name: AQIM_sample.csv
```

Notice that the values for `items_per_box` are under a `default` key. In the
future, the simulation may support other keys to vary the number of
`items_per_box` by commodity, origin, or port.

## Synthetic consignments

The main keys for the `parameter_based` consignment generator are the `min` and
`max` values of `boxes`. These values determine the range of sizes of
consignments within the simulation. In the example configuration below,
consignments will have 10 to 100 boxes per consignments.

```yaml
consignment:
  boxes:
    min: 10
    max: 100
```

The generator adds origin, flower (commodity type), and port (where consignment
was received). These are randomly selected from the lists specified in the
configuration. These values are not currently used, but may be used to configure
other parameters in the future (e.g., variable contamination rates by origin or
inspection efficacy by commodity).

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

## Create consignments to match an input file

To use a file of inspection records, set the `generation_method` to `input_file`
and specify the `file_type` and `file_name`. Currently, the options for
`file_type` are `F280` and `AQIM`. Additional type of inspection data can be
supported upon request, or you can format the inspection records in the same way
as F280 or AQIM data, described below. The `file_name` is a path absolute or relative to the place where the Python program is running.

```yaml
consignment:
  consignment_generator: input_file
  input_file:
    file_type: AQIM
    file_name: aqim_sample.csv
```

### F280-based consignments

Consignments in the simulation can be based on real F280 records. In that case,
a CSV file needs to be specified using the `file_name` key.

The CSV is expected to have the following columns:

* QUANTITY which will be used as number of items,
* PATHWAY which is used to determine the `items_per_box` value (case
  insensitive),
* REPORT_DT is used for date,
* COMMODITY as the flower (commodity type),
* ORIGIN_NM as origin, and
* LOCATION as port (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text fields
(`"`). The path is absolute or relative to the place where the Python program is
running.


### AQIM-based consignments

Consignments in the simulation can also be based on AQIM inspection records. In
that case, a CSV file needs to be specified using the `file_name` key.

The CSV is expected to have the following columns:

* UNIT which is used to specify the unit (must be items or boxes) used in
 QUANTITY.
* QUANTITY which is used as number of items or number of boxes depending on
 UNIT specified,
* CARGO_FORM which is used to determine the `items_per_box` value similar to
 PATHWAY in F280 (case insensitive),
* CALENDAR_YR is used for date (YYYY only),
* COMMODITY_LIST is used as the flower (commodity type),
* ORIGIN as origin, and
* LOCATION as port of entry (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text fields
(`"`). The path is absolute or relative to the place where the Python program is
running.

---

Next: [Contamination](contamination.md)
