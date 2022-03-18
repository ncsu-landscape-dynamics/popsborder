# Use cases

Here are examples of questions this tool can help to answer,
types of results it can give, and other use cases.

## What is the approximate contamination rate of a set of inspected consignments?

Given known inspection protocols (sample size and selection method) and
records containing the inspection outcomes, what is the approximate
contamination rate of the inspected consignments? By simulating
inspections using the same protocol and calibrating the contamination
parameters so that the simulated inspection outcomes match the actual
inspection outcomes, we can estimate the contamination rate present
in the actual consignments.

## What is the approximate slippage rate for an inspection protocol?

Given assumed contamination rates and consignment sizes, what percentage
of contaminates are not being intercepted by border inspections when using
various inspection methods? This information could be useful for estimating
propagule pressure for quarantine-significant pest species.

## what are the trade offs between effort and effectiveness for various inspection protocols?

For example, is the inspection success rate higher when we inspect fewer
consignments using hypergeometric random sampling, or when we inspect
all consignments using convenience sampling?

## How sensitive are the inspections to level of contamination?

Given a specific inspection protocol, what level of contamination
needs to be present in the consignments for us to detect it? Additionally,
how much pest needs to be present to raise alarms?

In the following example, we inspect two boxes of each consignment,
each containing between 1 and 50 boxes. We run the simulation with
different contamination rates and compare slippage rates.

| Contaminated boxes | Missed |
| ------------------ | -----: |
| 90%                |     1% |
| 80%                |     4% |
| 70%                |     9% |
| 60%                |    16% |
| 50%                |    24% |
| 40%                |    34% |
| 30%                |    47% |
| 20%                |    61% |
| 10%                |    77% |

## Will we intercept a newly emerging pest from a specific pathway?

Using a given inspection protocol, would we successfully intercept
a newly emerging pest? In this case, we would modify the parameters
that control how contamination in consignments from certain origin
countries are added based on another model projecting an emerging pest.

## Generate synthetic F280 records

Datasets like this one can be generated in case synthetic data with certain
properties or without privacy issues are needed:

| Date | Port  | Origin    | Flower    | Action   |
| ---- | ----- | --------- | --------- | -------- |
| 1    | RDU   | Estonia   | Gloriosa  | RELEASE  |
| 1    | Miami | Hawaii    | Gladiolus | RELEASE  |
| 2    | RDU   | Argentina | Actinidia | RELEASE  |
| 3    | Miami | Argentina | Gladiolus | RELEASE  |
| 3    | RDU   | Hawaii    | Ananas    | RELEASE  |
| 4    | Miami | Hawaii    | Acer      | RELEASE  |
| 5    | Miami | Taiwan    | Gladiolus | PROHIBIT |
| 5    | RDU   | Estonia   | Aegilops  | RELEASE  |

Example workflow is included in [Obtaining synthetic F280 records](synthetic_f280.md).

## See also

- Jupyter Notebooks, Python scripts, and Bash scripts included in the repository
- [Obtaining synthetic F280 records](synthetic_f280.md)
- [Outputs](outputs.md)

---

Next: [Consignments](consignments.md)
