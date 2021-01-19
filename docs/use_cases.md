# Use cases

Here are examples of questions this tool can help to answer,
types of results it can give, and other use cases.

## Synthetic F280 records

Datasets like this one can be generated in case synthetic data with certain
properties or without privacy issues are needed:

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

Example workflow is included in [Obtaining synthetic F280 records](synthetic_f280.md).

## Will we intercept a new pest?

Using a given system of border controls, will we intercept a new pest?
In this case, we would modify the parameters how pests in shipments from
a particular part of the world are added, e.g. by increasing their
probability, based on another model projecting immersion of such pest.

## How sensitive are our interception tests to level of infestation?

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


## Does a new import rule increase chance of missing a pest?

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

## How much pest is in the real shipments?

Given known import rules and sampling rates and the actual collected
data, how much pest is present in the actual shipments? By comparing the actual
collected data and the simulated results, we can determine, for given
sampling rates, how much pest is present in the actual shipments.

## Is is better to inspect more shipments or a random box?

Is our detection rate higher when we pick a random (randomly sampled)
box in fewer amount of shipments or when we just look at a box on
top (an easily accessible one) in more (or all) shipments?

## See also

* Jupyter Notebooks, Python scripts, and Bash scripts included in the repository
* [Obtaining synthetic F280 records](synthetic_f280.md)
* [Outputs](outputs.md)

---

Next: [Shipments](shipments.md)
