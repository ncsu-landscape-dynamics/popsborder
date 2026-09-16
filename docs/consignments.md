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
configuration. These values may be used to configure other simulation parameters
(e.g., variable contamination rates by origin).

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

The generator also adds a date to each consignment. Number of consignments
generated per day, i.e., number of consignments after which a new day begins,
is driven by `consignments_per_day` which defaults to 1.

## Create consignments to match an input file

To use a file of inspection records, set the `generation_method` to `input_file`
and specify the `file_type` and `file_name`. Currently, the options for
`file_type` are `F280`, `AQIM`, and `PIS`. Additional type of inspection data can be
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

- QUANTITY which will be used as number of items,
- PATHWAY which is used to determine the `items_per_box` value (case
  insensitive),
- REPORT_DT is used for date,
- COMMODITY as the flower (commodity type),
- ORIGIN_NM as origin, and
- LOCATION as port (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text fields
(`"`). The path is absolute or relative to the place where the Python program is
running.

### AQIM-based consignments

Consignments in the simulation can also be based on AQIM inspection records. In
that case, a CSV file needs to be specified using the `file_name` key.

The CSV is expected to have the following columns:

- UNIT which is used to specify the unit (must be items or boxes) used in
  QUANTITY.
- QUANTITY which is used as number of items or number of boxes depending on
  UNIT specified,
- CARGO_FORM which is used to determine the `items_per_box` value similar to
  PATHWAY in F280 (case insensitive),
- CALENDAR_YR is used for date (YYYY only),
- COMMODITY_LIST is used as the flower (commodity type),
- ORIGIN as origin, and
- LOCATION as port of entry (where consignment was received).

The CSV file should be comma-separated (`,`) using double quote for text fields
(`"`). The path is absolute or relative to the place where the Python program is
running.

---



### PIS-based consignments (`file_type: PIS`)

`PISConsignmentGenerator` handles **Plant Inspection Station (PIS)** data, which supports a hierarchical structure:

- Consignment → **sample units** → **inspection units** → **plants**.

Configure it using `generation_method: input_file` and `file_type: PIS`:

```yaml
consignment:
  generation_method: input_file
  input_file:
    file_type: PIS
    file_name: data/pis_inspections.csv
```

The CSV is expected to have the following columns (minimum set):

- `INSPECTION_NUMBER` - unique consignment/inspection ID.
- `PROPAGATIVE_MATERIAL_TYPE` - material type for this inspection unit.
- `SAMPLING_UNITS_FOR_INSPECTION_UNIT` - actual number of sample units associated the inspection unit (i.e., commodity line represented by a single row in the inspection data).
- `QUANTITY` - total number of plants in the inspection unit.
- `COUNTRY_OF_ORIGIN_NAME` - the origin country.
- `INSPECTION_LOCATION_NAME` - port/location (where the inspection was conducted).
- `PATHWAY` - transport pathway.
- `CREATED_DATETIME` - timestamp stored as a string in the format `YYYY-MM-DD HH:MM:SS.f` (`year-month-day, hour:minute:second.fraction`), where the fractional part represents sub‑second precision (e.g. `2020-12-04 22:25:26.4230000`).
- `producer_group` or `PRODUCER_NAME` - producer name; `producer_group` is used when present and not equal to `"Reference"`.
- A risk-unit label column, which must be **one** of the following (the first matching column name is used):
  - `RISK UNIT`
  - `RISK_UNIT`
  - `risk_unit`
  - `RISK_UNIT_NUMBER`  
  This column is used to group sample units into risk units.

Additional columns may be used depending on your `RiskUnitConfig` settings from `slippage_model_utils.UnitAttributes`.

- **Allowed/recognized columns** – the current `RiskUnitConfig` maps the following canonical 
attributes to CSV column names (see `slippage_model_utils/UnitAttributes.py`):
  - `material_type` → `PROPAGATIVE_MATERIAL_TYPE`
  - `producer_group` → `producer_group`
  - `origin` → `COUNTRY_OF_ORIGIN_NAME`
  - `port` → `INSPECTION_LOCATION_NAME`
  - `pathway` → `PATHWAY`
  - `median_qty_lt200` → `MEDIAN_QTY_LT200`
  - `frac_small` → `FRAC_SMALL`
  - `frac_small_gt07` → `FRAC_SMALL_GT07`
  - `any_small` → `ANY_SMALL`
  - `importer` → `IMPORTER_NAME`

- **Required columns** – the generator needs at minimum the core PIS columns 
listed above in the PIS file type description (e.g., `INSPECTION_NUMBER`, `QUANTITY`, `RISK_UNIT`, etc.).

- **How to discover which columns are usable** – open `slippage_model_utils/UnitAttributes.py` and 
inspect the `RiskUnitConfig.attribute_mapping` dictionary. Any key/value pair
in that dictionary represents a column that the generator will look for. 
Adding new entries to `attribute_mapping` (and optionally to `defaults` and `enabled_attributes`) is the 
way to support additional columns.

  **Example – adding a new boolean column `SAFE_ZONE_FLAG`**  

  ```python
  # In slippage_model_utils/UnitAttributes.py
  class RiskUnitConfig:
      attribute_mapping = {
          # existing mappings …
          "material_type": "PROPAGATIVE_MATERIAL_TYPE",
          # new column
          "safe_zone": "SAFE_ZONE_FLAG",
      }

      defaults = {
          # existing defaults …
          "material_type": None,
          # default for the new column
          "safe_zone": False,
      }

      enabled_attributes = [
          # existing attributes …
          "material_type",
          # enable the new attribute
          "safe_zone",
      ]
  ```

  After adding the three entries above, the generator will read the column
  `SAFE_ZONE_FLAG` from the input CSV (treating missing values as `False`) and
  expose it as the `safe_zone` attribute on each `RiskUnit` instance.


- **Behaviour when a column is absent** – the code uses the `defaults` 
mapping to supply a fallback value (e.g., `None` for strings, `False` for booleans).
No error is raised, so users can safely omit columns they do not have.

**What a *risk unit* represents**  
A *risk unit* groups together all commodity lines that are considered to
have the same risk profile for the purpose of sampling. 
By default, all rows that share the same origin and 
material type become one risk unit. This configuration allows a user to
set specific discriminators by station 
(e.g., adding `producer` to the defaults) to create distinct station-specific grouping
strategies. The hypergeometric calculator then treats each risk unit independently, 
applying the detection and confidence levels from the compliance lookup table 
to compute the number of samples required for that risk unit group.  

#### Generating Synthetic Consignments

To generate synthetic PIS‑style consignments you need the following inputs. 
Items marked **required** must be supplied 
(or the script will fall back to built‑in defaults); items marked **optional** can be omitted.

- **Configuration file** (*required*) – path to a PoPS Border configuration YAML 
(e.g., `config_rbs.yml`).
- **Training data** (*required*) – a CSV file containing the real PIS inspection 
records that the generator will model (e.g., `train.csv`) with the required columns specified above.
This is the *base PIS dataset* from which synthetic consignments are derived.
- **Compliance table** (*required*) – CSV file used for risk‑unit calculations
(e.g., `compliance_table.csv`). If omitted the script defaults 
to `development_files/slippage_data/compliance_table.csv`.
- **Producer‑group mapping** (*required*) – CSV that maps raw producer
names to a grouping identifier indicated by columns
`PRODUCER_NAME` (string) and `grouping` (float), respectively.
- **Output file name** (*optional*) – name (or path) for the generated synthetic 
CSV (e.g., `Synthetic_Data.csv`). Defaults to `Synthetic_Data_TEST.csv`.
- **Engineered‑features flag** (*optional*) – `--create-engineered-features` to invoke additional
R‑based feature creation.
- **Producer‑importer training data** (*required*)  – CSV required only when
`--create-engineered-features` is used (e.g., `producer_importer_training.csv`). This should correspond
to a file similar to the PIS input data described above where each row represents a *commodity*. 
This file should contain the columns `action` (binary representing if action was taken on the ),
`PRODUCER_GROUP_NAME1` (representing a raw producer name.  Note that in the RBS modeling approach, this was
the first observed producer name found among the inspection units after being grouped by
`INSPECTION_NUMBER`, `COUNTRY_OF_ORIGIN_NAME`, and `PROPAGATIVE_MATERIAL_TYPE`), and 
`IMPORTER_NAME1` (representing a raw importer name.  Note that in the RBS modeling approach, this was
the first observed importer name found among the inspection units after being grouped by
`INSPECTION_NUMBER`, `COUNTRY_OF_ORIGIN_NAME`, and `PROPAGATIVE_MATERIAL_TYPE`).

##### Synthetic Consignments Generation Workflow

1. Run the synthetic consignment generation script: `python -m slippage_model_utils.generate_synthetic_consignments`.
Additional command line flags can be added as below (see table for more descriptions of these flags).

   ```bash
   python -m slippage_model_utils.generate_synthetic_consignments \
       --config config_rbs.yml \
       --num-consignments 100 \
       --synthetic-data-file-name Synthetic_Data.csv \
       --producer-group-mapping-path path/to/producer_group_mapping.csv \
       --compliance-table-path path/to/compliance_table.csv \
       --training-data-path path/to/train.csv \
       [--create-engineered-features] \
       [--producer-importer-training-path path/to/producer_importer.csv]
   ```

   The script loads the PoPS Border configuration, reads the training data, generates the requested number of synthetic consignments using the *sequential* sampling method, optionally creates engineered features, and writes the result to the specified CSV file.

2. Use the generated file as the input for the simulation by setting:

   ```yaml
   consignment:
     generation_method: input_file
     input_file:
       file_type: PIS
       file_name: <path-to-generated-file>
   ```

#### Command‑line arguments

| Flag | Description | Example |
|------|-------------|---------|
| `--config` | Configuration file (top‑level repo) | `config_rbs.yml` |
| `--num‑consignments` | Number of consignments to generate | `100` |
| `--synthetic‑data‑file‑name` | Name of the CSV file to write | `Synthetic_Data.csv` |
| `--producer‑group‑mapping‑path` | Path to producer‑group mapping CSV | `data/producer_group_mapping.csv` |
| `--compliance‑table‑path` | Path to the compliance table CSV | `data/compliance_table.csv` |
| `--training‑data‑path` | Path to training data CSV (base PIS data) | `data/train.csv` |
| `--create‑engineered‑features` | If present, engineered features are added via R code | *(flag only, no value)* |
| `--producer‑importer‑training‑path` | Path to additional training data for engineered features | `data/producer_importer_training.csv` |

Next: [Contamination](contamination.md)
