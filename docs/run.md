# Running the simulation

The two basic ways to run the simulation are a Python package and command line interface. Both interfaces take simulation parameters as a configuration file and several other user inputs as function arguments or command line arguments.

The configuration file contains all parameters needed for a single simulation run. The package documentation explains the configuration parameters in detail. The configuration format is YAML which is both human and machine readable and writable and JSON is supported as an alternative. The configuration file consists of a set of key and value pairs, which specify the parameters used for consignment generation, contamination, and inspection.
The path to the configuration file must be provided as a function or command line argument, along with the number consignments and stochastic runs to simulate.

You can use the package from the command line (using the command line interface
of the Python package) or directly from Python (within an IDE or Jupyter Notebook).
While calling the functions in Python is flexible and advantageous for incorporating the simulation in a larger analytical workflow, the command line interface is straightforward and useful for exploring different behaviors of the consignment inspections or the simulation itself.
Python API is documented in docstrings (available in code or through Python help function). For running simulation in the command line,
see a dedicated [CLI page](cli.md) in this documentation.

For running many scenarios at once, a Python function, `popsborder.scenarios.run_scenarios` is provided which in addition to the YAML configuration file also takes a table of scenario configurations as a XLSX file, CSV file, or other spreadsheet formats. Each row in the scenario table represents one scenario and each column contains the configuration parameter values to be modified. Column names determine which parts (keys) of the YAML configuration file are modified. Nested keys are specified using forward slashes (`key/subkey/subsubkey`). The values can use JSON syntax to specify lists or nested values (e.g., `[1, 2]`). The values returned from the function can be used for further processing or visualization in Python. Alternatively, these can be saved to a file using Python and processed elsewhere.

Example scripts and (Jupyter) notebooks are included in the code repository.
The notebooks are extremely useful for visualization of the simulation outcomes.
You can try the notebooks online without any instalation using [Binder](binder.md).

---

Next: [Outputs](outputs.md)
