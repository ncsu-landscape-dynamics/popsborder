# Shipment configuration

The shipments can be either purely synthetic or based on existing F280
records. Configuration for the shipments is under the `shipment` key
in the configuration file.

## Synthetic shipments

The two main keys for configuration of the synthetic shipment generator
are `boxes` and `stems_per_box`. The `min` and `max` values of `boxes`
determine the range of sizes of shipments within the simulation.
The `default` value of `stems_per_box` determines how many stems are in
one box. An example configuration with shipments with 10 to 100 boxes
and 200 stems per box, i.e., 2000 to 20,000 stems per shipments follows.

```yaml
shipment:
  boxes:
    min: 10
    max: 100
  stems_per_box:
    default: 200
```

Currently, no further settings for `stems_per_box` is possible, but in
the future further settings might be added.

The generator adds origin, flower (commodity type), and port (where
shipment was received). These are randomly selected from the lists
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

## F280-based shipments

Shipments in the simulation can be based on real F280 records. In that
case, a CSV file needs to be specified.

The CSV is expected to have the following columns:
 * QUANTITY which will be used as number of stems,
 * PATHWAY which is used to determine the `stems_per_box` value
   (comparison is case insensitive),
 * REPORT_DT is used for date,
 * COMMODITY as the flower (commodity type),
 * ORIGIN_NM as origin, and
 * LOCATION as port (where shipment was received).

The CSV file should be comma-separated (`,`) using double quote for text
fields (`"`). The path is absolute or relative to the place where the
Python program is running.

The F280 records contain only the number of stems. To create the boxes
(of stems) for the simulation, `stems_per_box` need to be specified.
Optionally, specific values for `air` and `maritime` can be added.
The following is a configuration with file called `F280_sample.csv`.
If the pathway is `air`, one box has 50 stems, 500 for `maritime`,
and 100 for other pathways.

```yaml
shipment:
  f280_file: F280_sample.csv
  stems_per_box:
    default: 100
    air:
      default: 50
    maritime:
      default: 700
```

Notice that the values for `stems_per_box` are under additional key
`default`. In the future, the simulation may support other keys for
specific commodities, origins, or ports.

---

Next: [Pests](pest.md)
