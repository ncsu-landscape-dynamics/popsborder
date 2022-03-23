# Running the simulation

The two basic ways to run the simulation are a Python package and command line
interface. Both interfaces take simulation parameters as a configuration file
and several other user inputs as function arguments or command line arguments.

## Configuration

The configuration file contains all parameters needed for a single simulation
run. The package documentation explains the configuration parameters in detail.
The configuration format is key-value pairs structured hierarchically. The
configuration file consists of a set of key and value pairs, which specify the
parameters used for consignment generation, contamination, and inspection. Here,
we will refer to this configuration as base configuration to distinguish it from
configurations in the scenario table introduced later in this document.

The configuration file can be in YAML, JSON, XLSX, ODS, or CSV. In YAML and JSON
the hierarchy of keys is represented directly, for example, in a YAML file,
generation method for consignments is represented as:

```yaml
consignment:
  generation_method: parameter_based
```

In XLSX, ODS, and CSV, the hierarchy of keys is specified using forward slashes
(`key/subkey/subsubkey`), for example, in a CSV file, the above configuration is
represented as:

```csv
consignment/generation_method,parameter_based
```

XLSX, ODS, and CSV are common spreadsheet (tabular) formats while YAML is a
common configuration format. YAML which is both human and machine readable and
writable. JSON is provided here as broadly supported alternative to YAML.

The path to the base configuration file must be provided as a function or
command line argument, possibly with other values for the spreadsheet formats,
along with the number consignments and stochastic runs to simulate.

## Running

You can use the package from the command line (using the command line interface
of the Python package) or directly from Python (within an IDE or Jupyter
Notebook). While calling the functions in Python is flexible and advantageous
for incorporating the simulation in a larger analytical workflow, the command
line interface is straightforward and useful for exploring different behaviors
of the consignment inspections or the simulation itself. Python API is
documented in docstrings (available in code or through Python help function).
For running simulation in the command line, see a dedicated [CLI page](cli.md)
in this documentation.

## Scenarios

For running many scenarios at once, a Python function,
`popsborder.scenarios.run_scenarios` is provided which in addition to the base
configuration file also takes a table of scenario configurations as a XLSX file,
CSV file, or other spreadsheet formats. Each row in the scenario table
represents one scenario and each column contains the configuration parameter
values to be modified. Column names determine which parts (keys) of the base
configuration file are modified. Nested keys are specified using forward slashes
(`key/subkey/subsubkey`) as for the base configuration in the spreadsheet
formats described above. The values can use JSON syntax to specify lists or
nested values (e.g., `[1, 2]`). The values returned from the function can be
used for further processing or visualization in Python. Alternatively, these can
be saved to a file using Python and processed elsewhere.

## Including other configuration files

For complex scenarios where a significant portion of the configuration changes,
it is advantageous to use a separate configuration files for the variable portion
of the configuration. This is especially useful when the (tree) structure of the
configuration changes and thus would be difficult to express by values in a scenario
configuration under a single key `key/subkey/subsubkey` (you can include a complex JSON
structure as the value, but it would be hard to read and maintain).

For example, when `consignments` under `contamination` significantly differ for each scenario,
i.e., more than just few values are changed, the whole list of contamination settings
for consignments can be placed in a separate file and this file can be included. In this case,
the main configuration file contains:

```yaml
contamination:
  consignments:
    include_file:
      file_name: consignments_list.yml
```

The included `consignments_list.yml` file with the list of contamination settings
for consignments can look like this:

```yaml
- commodity: Liatris
  origin: Netherlands
  contamination:
    arrangement: random_box
- commodity: Gerbera
  origin: Netherlands
  contamination:
    arrangement: random
- commodity: Hyacinthus
  origin: Israel
  contamination:
    arrangement: random
```

For scenario configuration which is in tabular form with column headers as keys,
the file inclusion for three scenarios would look like this:

| name       | contamination/consignments/include_file/file_name |
| ---------- | ------------------------------------------------- |
| Scenario A | consignments_list_scenario_a.yml                  |
| Scenario B | consignments_list_scenario_b.yml                  |
| Scenario C | consignments_list_scenario_c.yml                  |

The included file can be in the same formats as the main configuration file,
i.e., hierarchical (in YAML or JSON) or tabular (in XLSX, ODS, CSV).
For spreadsheet formats (XLSX, ODS) additional values should be provided for
`sheet`, `key_column`, and `value_column` in the same way as this is done
for the main configuration. Each scenario can have different combination of
`sheet`, `key_column`, and `value_column` used, so for example, the `file_name`,
`sheet`, and `key_column` can be fixed, but each scenario can have different
`value_column`. In this example, assuming the other settings is in the
base configuration file, the `include_file` for each scenario can look
like this:

| name       | contamination/consignments/include_file/value_column |
| ---------- | ---------------------------------------------------- |
| Scenario A | A                                                    |
| Scenario B | B                                                    |
| Scenario C | C                                                    |

Additionally, for cases when the file contains a list of mappings (dictionaries)
as in the above example, the file can be in tabular form with keys being
column names similarly to the scenario table. In this case, value
`list` needs to be specified for an additional `file_format` key.
This value can be then specified in the base configuration (while the
scenario configuration specifies only the file name):

```yaml
contamination:
  consignments:
    include_file:
      file_name: consignments_list.csv
      file_format: list
```

The included `consignments_list.csv` file with the list of contamination settings
for consignments organized as a list (`file_format: list`) can look like this:

| commodity  | origin      | contamination/arrangement |
| ---------- | ----------- | ------------------------- |
| Liatris    | Netherlands | random_box                |
| Gerbera    | Netherlands | random                    |
| Hyacinthus | Israel      | random                    |

When the configuration is read, this table is translated to a list under
`contamination/consignments`.

## Examples

Example scripts and (Jupyter) notebooks are included in the code repository. The
notebooks are extremely useful for visualization of the simulation outcomes. You
can try the notebooks online without any installation using [Binder](binder.md).

---

Next: [Outputs](outputs.md)
