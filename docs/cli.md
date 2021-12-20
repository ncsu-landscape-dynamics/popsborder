# Command line interface

## Requirements

The Python code runs with Python 3. (Python 2.7 is not supported.)

The Python *json* and *csv* packages are part of the Python standard library,
while the *PyYAML* package needs to be installed to support YAML,
*openpyxl* to support XLSX, and *Pandas* together with *odfpy* to support ODS
(all are included as dependencies when the install the *popsborder* package is
installed).

If you do not install the package or modify Python path, you will need to
run in from the directory with the *popsborder* package, i.e., the root
directory of the repository.
If you install the package using *pip*, *pip* will take of the
dependencies and it will work in any directory.

## Running

The configuration is provided in a file which is specified as a command line
parameter `--config-file`. The configuration format is YAML (extensions `.yml`
or `.yaml`), JSON (extension `.json`), XLSX (`.xlsx`), ODS (`.ods`), or CSV
(`.csv`).

For spreadsheet (tabular) formats (XLSX, ODS, and CSV), you need specify
`sheet`, `key_column`, and `value_column` together with the file name in the
`--config-file` separated by `::` from the file name as key-value pairs
where key and value are separated by `=` and individual keys are separated by `,`.

## Examples

Direct run of the simulation with 1000 consignments repeated 20 times:

```
python -m popsborder --num-simulations 20 --num-consignments 1000 --config-file config.yml
```

In the example above, replace `config.yml` by a full path to the file. Full path
may be an absolute path in the file system with all directories (folders)
included, a relative path from the current directory to the file, or just the
file name as in the example if the file is in the current directory.

Run of the simulation once with 100 consignments with a tabular config in a CSV
file where parameter keys and values are in the first (A) and second (B) columns:

```sh
python -m popsborder --num-consignments 100 --config-file config.csv::key_column=1,value_column=2
```

Here we use XLSX specifying a sheet and specifying columns using letters:

```sh
python -m popsborder --num-consignments 100 --config-file "config.xlsx::sheet=Sheet 2,key_column=A,value_column=B"
```

For a sheet with spaces in the name as in the example above, simply quote the
whole command-line argument as you would quote spaces in a file name.


## Command line options

Get all command line options for the simulation by running:

```
python -m popsborder --help
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
