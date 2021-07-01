# Pathway Simulation

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ncsu-landscape-dynamics/pathways-simulation/master?urlpath=lab/tree/example.ipynb)
![CI](https://github.com/ncsu-landscape-dynamics/pathways-simulation/workflows/CI/badge.svg)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Simulation for evaluation of pathways which generates synthetic shipment
data and performs inspection on them. It is using the following model
to understand the system:

```math
f(x) -> y
```

where *x* represents all shipments with all information about them
such as the level of infestation, *f* is a sampling function,
i.e. import procedure used at the port,
and *y* represents the resulting record in the database.

Since the simulation is generating *x*, we can compute:

```math
r = g(y) / g(x)
```

where *x* and *y* are defined in the same way as above,
*g* is a function giving level of infestation in each set
(e.g. number of shipments with a pest),
and *r* is the success rate in detecting infestation
using the function *f* from above.

## Use cases

This simulation tool can help to answer various questions about influence
of inspection protocols or pest or contaminant presence on inspection outcome.
For example, the tool can generate synthetic data representing consignments
with variations in contamination rates and test how different inspection
methods influence inspection outcomes.
See more use cases in a dedicated [documentation section](docs/use_cases.md).

## Documentation

An example of how the simulation interface works is in
[this Jupyter notebook](example.ipynb).

To run the code without installing anything use Binder:

[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ncsu-landscape-dynamics/pathways-simulation/master?urlpath=lab/tree/example.ipynb)

If you are not familiar with Binder, see
[our short intro](docs/binder.md).

Documentation is included in the [docs](docs/) directory.
[command line interface](docs/cli.md)
and [shipment configuration](docs/shipments.md)
pages are good ones to start with.

## Install

Besides Python, you will need *pipenv* which is usually installed using *pip*.
The dependencies of this package will be installed into the virtual environment
created by *pipenv*. Download this repository (e.g., as ZIP and unpack it).
In the directory with the code with *pipenv* installed, run:

```
pipenv install
```

Additionally, you may want to install Jupyter and visualization libraries
to that environment. See the contributing section below for more options.

## Contributing

To contribute to this repository it is handy to have a several packages
installed and then run certain tools before each commit or pull request,
however you will have a chance to see and correct the errors also after
you open a pull request.

### Install everything using pipenv

```
pipenv install --dev
```

### Install development dependencies manually

Install the following packages:

```
flake8 pylint black pytest pytest-datadir
```

Install these using *pip* or *conda* possibly into a (virtual)
environment.

### Run tests

To run these from command line use:

```
flake8 .
pylint popsborder
black .
pytest tests/
```

### Modifying notebooks

We store computed notebooks as they serve as documentation and
examples.
After modification, notebooks should be recomputed, e.g., by
*Restart kernel and run all cells* to ensure that the notebook runs
with the cells executed in order and that there are minimal changes
to the notebook (e.g., executed cell numbers).

The standard `git diff` is not particularly useful for `.ipynb` files,
especially for computed ones, but the rendered file can be viewed in PR
and *nbdiff* in command line can show a human-readable difference.

## Authors

* Vaclav Petras, NCSU Center for Geospatial Analytics
* Kellyn P. Montgomery, NCSU Center for Geospatial Analytics
* Anna Petrasova, NCSU Center for Geospatial Analytics

## License

The simulation code is open source under GNU GPL >=v2
(see the LICENSE file for details).

## Acknowledgment and Disclaimer

This research is funded by USDA APHIS. The findings do not necessarily
represent the views of USDA APHIS.

Please note that this is a simulation and it needs to be calibrated
to give any realistic or actionable results. Results presented here
are examples for demonstration purposes only.
