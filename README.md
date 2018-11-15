# Pathway Simulation

Simulation for evaluation of pathway which generates synthetic shipment
data and performs inspection on them.

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

### Does a new import rule increase chance of missing a pest?

With a given a (example) configuration of the shipment generation and
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
(here 50%m but active CFRP), if we increase number of boxes we inspect
in each shipment, our chances of detecting the pest increase:

| Boxes | Missed |
| ----- | ------ |
| 0     | 100%   |
| 1     | 54%    |
| 2     | 31%    |
| 3     | 20%    |
| 4     | 15%    |
| 5     | 12%    |

## Documentation

The Python code runs with both Python 2.7 and Python 3.

The configuration is provided in a file specified as a command line
parameter. The configuration format is JSON (extension `.json`) or YAML
(extensions `.yml` or `.yaml`). The Python `json` package is part of
the Python standard library while the `yaml` package needs to be
installed (as of Python 3.6).
