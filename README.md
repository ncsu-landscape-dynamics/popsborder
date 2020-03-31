# Pathway Simulation

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
(e.g. number of shipmets with a pest),
and *r* is the success rate in detecting infestation
using the function *f* from above.

## Types of questions and results

Here are examples of questions this tool can help to answer and
types of results it can give.

## Synthetic F280 records

| Date | Port | Origin | Flower | Action |
| ---- | ---- | ------ | ------ | ------ |
| 1 | RDU | Estonia | Gloriosa | RELEASE |
| 1 | Miami | Hawaii | Gladiolus | RELEASE |
| 2 | RDU | Argentina | Actinidia | RELEASE |
| 3 | Miami | Argentina | Gladiolus | RELEASE |
| 3 | RDU | Hawaii | Ananas | RELEASE |
| 4 | Miami | Hawaii | Acer | RELEASE |
| 5 | Miami | Taiwan | Gladiolus | PROHIBIT |
| 5 | RDU | Estonia | Aegilops | RELEASE |

### Will we intercept a new pest?

Using a given system of border controls, will we intercept a new pest?
In this case, we would modify the parameters how pests in shipments from
a particular part of the world are added, e.g. by increasing their
probability, based on another model projecting immersion of such pest.

### How sensitive are our interception tests to level of infestation?

Given a specific set of import rules, how much pest needs to be present
in the shipments for us to detect it? Additionally, how much pest needs
to be present to raise alarms?

In the following example, we were checking two boxes of each shipment,
one shipment contained between 1 and 50 boxes and CRFP was not active.
We ran the simulations with different ratio of infested boxes in one
infested shipment.

| Infested boxes | Missed |
| -------------- | ------ |
| 90%            |  1%    |
| 80%            |  4%    |
| 70%            |  9%    |
| 60%            | 16%    |
| 50%            | 24%    |
| 40%            | 34%    |
| 30%            | 47%    |
| 20%            | 61%    |
| 10%            | 77%    |


### Does a new import rule increase chance of missing a pest?

With a given (example) configuration of the shipment generation and
the CFRP, we can get a table like this relating number of flowers in
CFRP and percentage of shipments with undiscovered pests
(total number of flowers is 6):

| Flowers | Missed |
| ------- | ------ |
| 0       | 24%    |
| 1       | 24%    |
| 2       | 26%    |
| 3       | 29%    |
| 4       | 31%    |
| 5       | 33%    |
| 6       | 36%    |

If we are increasing the maximum number of boxes we don't check as part
of CFRP (i.e. we check all above that size), we also increase the
percentage of shipments with undiscovered pests:

| Boxes | Missed |
| ----- | ------ |
| 0     | 24%    |
| 1     | 24%    |
| 2     | 25%    |
| 5     | 28%    |
| 10    | 31%    |
| 20    | 39%    |
| inf   | 62%    |

With a given ratio of boxes with pest in a shipment with pests
(here 50%, but active CFRP), if we increase number of boxes we inspect
in each shipment, our chances of detecting the pest increase:

| Boxes | Missed |
| ----- | ------ |
| 0     | 100%   |
| 1     | 54%    |
| 2     | 31%    |
| 3     | 20%    |
| 4     | 15%    |
| 5     | 12%    |

### How much pest is in the real shipments?

Given known import rules and sampling rates and the actual collected
data, how much pest is present in the actual shipments? By comparing the actual
collected data and the simulated results, we can determine, for given
sampling rates, how much pest is present in the actual shipments.

### Is is better to inspect more shipments or a random box?

Is our detection rate higher when we pick a random (randomly sampled)
box in fewer amount of shipments or when we just look at a box on
top (an easily accessible one) in more (or all) shipments?

## Documentation

### Running the code

The Python code runs with both Python 2.7 and Python 3.

The configuration is provided in a file which is specified as a command line
parameter. The configuration format is JSON (extension `.json`) or YAML
(extensions `.yml` or `.yaml`). The Python `json` package is part of
the Python standard library while the `yaml` package needs to be
installed (as of Python 3.8).

A simple run (runs) of the simulation with predefined values
covering both success rate in detection of pests and generation of F280
records:

```
./run.sh
```

Generating a sample dataset with F280 records only:

```
./generate_synthetic_F280_dataset.sh synthetic_records.csv 1000
```

Direct run of the simulation with 1000 shipments repeated 20 times:

```
python -m pathways --num-simulations 20 --num-shipments 1000 --config-file config.yml
```

Get all command line options for the simulation by running:

```
python -m pathways --help
```

### Configuration

#### Pests

The pest arrangement within the shipment can be determined by:

```
pest:
  arrangement: random
```

The arrangement can be `random` for uniform random distribution,
`clustered` for one or more pest clusters within stems of the shipment,
and `random_box` for one or more random boxes having pest.

For arrangement `random` and `clustered`, the infestation rate can be
determined by:

```
pest:
  infestation_rate:
    distribution: beta
    parameters:
    - 4
    - 60
```

The infestation rate can be also set using a fixed value (rather than
random values based on the given distribution):

```
pest:
  infestation_rate:
    distribution: fixed_value
    value: 0.05
```

The `random` arrangement does not have any further configuration besides
`infestation_rate`.

The settings for `clustered` is:

```
  clustered:
    max_stems_per_cluster: 10
    distribution: gamma
    parameters:
    - 4
    - 2
```

The cluster size in terms of number of stems is limited by
`max_stems_per_cluster`. If `max_stems_per_cluster` is exceeded, more
than one cluster is generated so that number of stems in each cluster
conforms to this limit.

The distribution for clustered can be `gamma`, `random`, and `continuous`
and it drives the placement of infested stems within a cluster.
The `gamma` option uses the gamma distribution and takes two parameters.
The `random` option uses the uniform random distribution. The cluster
width is defined by the first and only parameter of this distribution.
The `continuous` distribution does not have any parameters and produces
infested stems next to each other so the number of infested stems in the
cluster is the same as the width of the cluster.

The settings for `random_box` is:

```
pest:
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

Probability of shipment being infested is driven by `probability`
while the number of boxes infested within a shipment is driven by `ratio`.
The infestation within one box is determined by `in_box_arrangement`
which can have values `all`, `first`, `one_random`, and `random`.
For `all`, all stems within a box are infested.
With `first`, only the first stem in the box will get pest.
`one_random` is similar to `first`, but a random stem is picked to get
pest.
The `random` in-box arrangement will place pests in a box using uniform
random distribution. The number of pests to be placed is determined
using the distribution configured using the `infestation_rate` key
which takes meaning *infestation rate within a box* instead of its usual
meaning *infestation rate within a shipment*.
In that case, the configuration may look like this:

```
pest:
  infestation_rate:
    distribution: beta
    parameters: [20, 30]
  random_box:
    probability: 0.2
    ratio: 0.5
    in_box_arrangement: all
```

#### Disposition codes

Here is an example with disposition codes close to what is used in F280:

```
disposition_codes:
  inspected_ok: IRMR
  inspected_pest: FUAP
  cfrp_inspected_ok: IRAR
  cfrp_inspected_pest: FUAR
  cfrp_not_inspected: REAR
```

#### Inspection

Cut Flower Release Program (CFRP):

```
release_programs:
  naive_cfrp:
    flowers:
    - Hyacinthus
    - Gerbera
    - Rosa
    - Actinidia
    max_boxes: 10  # do not apply to shipments larger than
```

Tailgate with *n* boxes:

```
inspection:
  first_n_boxes: 2
```

### Obtaining pre-computed sample database records

#### Download using a web browser

To download sample synthetic database records (F280)
by clicking [this link](https://ncsu-landscape-dynamics.github.io/pathways-simulation/synthetic_records.csv).

#### Download using command line

Alternatively, in a Linux command line (or in an equivalent environment),
you can execute (assuming you have `wget` installed):

```
wget https://ncsu-landscape-dynamics.github.io/pathways-simulation/synthetic_records.csv
ls synthetic_records.csv
```

The last command (`ls`) just confirms that you have the data downloaded
and uncompressed. If you need some troubleshooting,
the following example might be helpful (relying of the program `file`).

```
$ file synthetic_records.csv
synthetic_records.csv: ASCII text
```

## Authors

* Vaclav Petras, NCSU Center for Geospatial Analytics
* Anna Petrasova, NCSU Center for Geospatial Analytics
* Kellyn P. Montgomery, NCSU Center for Geospatial Analytics

## License

The simulation code is open source under GNU GPL >=v2
(see the LICENSE file for details).

## Acknowledgment and Disclaimer

This research is funded by USDA APHIS. The findings do not necessarily
represent the views of USDA APHIS.

Please note that this is a simulation and it needs to be calibrated
to give any realistic or actionable results. Results presented here
are examples for demonstration purposes only.
