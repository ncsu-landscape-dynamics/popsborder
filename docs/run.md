# Running the simulation

There are two basic ways are a Python package and command line interface. Both interfaces take simulation parameters as a configuration file and several other user inputs as function arguments or command line arguments.

The configuration file contains all parameters needed for a single simulation run
and most of the documentation refers to it. The configuration format is YAML which is both human and machine readable and writable and JSON is supported as an alternative. The configuration file consists of a set of key and value pairs, which specify the parameters used for consignment generation, contamination, and inspection.
The configuration file must be provided as a function or command line argument, along with the number consignments and stochastic runs to simulate.

You can either use the package from the command line or Python.
While calling the functions in Python is flexible and advantageous for incorporating the simulation in a larger analytical workflow, the command line interface is straightforward and useful for exploring different behaviors of the consignment inspections or the simulation itself.
Python API is documented in docstrings (available in code or through Python help function). For running simulation in the command line,
see a dedicated [CLI page](cli.md) in this documentation.

For running many scenarios at once, a Python function, `pathways.scenarios.run_scenarios` is provided which in addition to the YAML configuration file also takes a table as a CSV file where each line represents one scenario and modifies the values in the configuration file. The CSV column names determine which parts of the YAML configuration file are set or replaced. Nested keys are specified using forward slashes (`key/subkey/subsubkey`). The values can use JSON syntax to specify lists or nested values (e.g., `[1, 2]`). The values returned from the function can be used for further processing or visualization in Python. Alternatively, these can be saved to a file using Python and processed elsewhere.

Example scripts and (Jupyter) notebooks are included in the code repository.
The notebooks are extremely useful for visualization of the simulation outcomes.
You can try the notebooks online without any instalation using [Binder](binder.md).

---

Next: [Outputs](outputs.md)
