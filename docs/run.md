# Running the simulation

The two basic ways to run the simulation are a Python package and command line interface. Both interfaces take simulation parameters as a configuration file and several other user inputs as function arguments or command line arguments.

The configuration file contains all parameters needed for a single simulation run. The package documentation explains the configuration parameters in detail. The configuration format is key-value pairs structured
hierarchically. The configuration file consists of a set of key and value pairs, which specify the parameters used for consignment generation, contamination, and inspection.
Here, we will refer to this configuration as base configuration to distinguish it from configurations in the scenario table introduced later in this document.

The configuration file can be in YAML, JSON, XLSX, ODS, or CSV. In YAML and JSON the hierarchy of keys is represented directly, for example, in a YAML file, generation method for consignments is represented as:

```yaml
consignment:
  generation_method: parameter_based
```

In XLSX, ODS, and CSV, the hierarchy of keys is specified using forward slashes (`key/subkey/subsubkey`), for example, in a CSV file, the above configuration is represented as:


```csv
consignment/generation_method,parameter_based
```

XLSX, ODS, and CSV are common spreadsheet (tabular) formats while YAML is a common configuration format.
YAML which is both human and machine readable and writable. JSON is provided here as broadly supported alternative to YAML.

The path to the base configuration file must be provided as a function or command line argument, possibly with other values for the spreadsheet formats, along with the number consignments and stochastic runs to simulate.

You can use the package from the command line (using the command line interface
of the Python package) or directly from Python (within an IDE or Jupyter Notebook).
While calling the functions in Python is flexible and advantageous for incorporating the simulation in a larger analytical workflow, the command line interface is straightforward and useful for exploring different behaviors of the consignment inspections or the simulation itself.
Python API is documented in docstrings (available in code or through Python help function). For running simulation in the command line,
see a dedicated [CLI page](cli.md) in this documentation.

For running many scenarios at once, a Python function, `popsborder.scenarios.run_scenarios` is provided which in addition to the base configuration file also takes a table of scenario configurations as a XLSX file, CSV file, or other spreadsheet formats. Each row in the scenario table represents one scenario and each column contains the configuration parameter values to be modified. Column names determine which parts (keys) of the base configuration file are modified. Nested keys are specified using forward slashes (`key/subkey/subsubkey`) as for the base configuration in the spreadsheet formats described above. The values can use JSON syntax to specify lists or nested values (e.g., `[1, 2]`). The values returned from the function can be used for further processing or visualization in Python. Alternatively, these can be saved to a file using Python and processed elsewhere.

Example scripts and (Jupyter) notebooks are included in the code repository.
The notebooks are extremely useful for visualization of the simulation outcomes.
You can try the notebooks online without any instalation using [Binder](binder.md).

---

Next: [Outputs](outputs.md)
