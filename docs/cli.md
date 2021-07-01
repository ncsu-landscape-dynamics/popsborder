# Command line interface

## Requirements

The Python code runs with Python 3. (Python 2.7 is not supported.)

The configuration is provided in a file which is specified as a command line
parameter. The configuration format is JSON (extension `.json`) or YAML
(extensions `.yml` or `.yaml`). The Python `json` package is part of
the Python standard library while the `yaml` package needs to be
installed (as of Python 3.8).

Unless you install the package or modify Python path, you will need to
run in from the directory with the *pops_border* package, i.e., the root
directory of the repository.

If you install the package using *pip*, *pip* will take of the
dependencies and it will work in any directory. 

## Example

Direct run of the simulation with 1000 consignments repeated 20 times:

```
python -m pops_border --num-simulations 20 --num-consignments 1000 --config-file config.yml
```

## Command line options

Get all command line options for the simulation by running:

```
python -m pops_border --help
```

## Post-processing the output

The following sample script included in the repository shows simple
runs of the simulation with predefined values
covering both success rate in detection of contaminants and generation of F280
records:

```
./examples/bash/bash_examples.sh
```

---

Next: [Consignments](consignments.md)
