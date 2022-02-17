# Cut Flower Release Program

The _Cut Flower Release Program_ can be used to skip inspection of qualifying consignments.
It is specified under `release_programs` using the key `cfrp`, for example:

```yaml
release_programs:
  cfrp:
```

Consignments which qualify for the program may or may not be marked for inspection depending on
an inspection schedule. Non-qualifying consignments are always marked for inspection.

## Schedule

The main component of the program is a schedule which
specifies the _Flower of the Day_ (FotD). This is a flower (or generally, commodity)
to inspect on a given day. At the same time, the schedule determines which flowers
qualify for the program.

The schedule is in tabular format. The following table shows three days of the schedule:

| Date       | Commodity     | ORIGIN_NM   |
| ---------- | ------------- | ----------- |
| 2014-10-01 | Liatris       | Ecuador     |
| 2014-10-02 | Sedum         | Netherlands |
| 2014-10-03 | Bouquet, Rose | Colombia    |

The same schedule in a CSV format:

```csv
"DATE","COMMODITY","ORIGIN_NM"
"2014-10-01","Liatris","Ecuador"
"2014-10-02","Sedum","Netherlands"
"2014-10-03","Bouquet, Rose","Colombia"
```

The schedule file is specified in a YAML configuration file as follows:

```yaml
release_programs:
  cfrp:
    schedule:
      file_name: schedule.csv
```

And in tabular configuration like this:

| Parameter keys                           | Value        |
| ---------------------------------------- | ------------ |
| release_programs/cfrp/schedule/file_name | schedule.csv |

Note that the column names in the schedule file must be `date`, `commodity`,
and `origin_nm`. However, the case does not matter, so all of `date`, `Date`,
and `DATE` are allowed.

Format of the date can be specified using the `date_format` key under `schedule`.
The value is a string with [format codes](https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
for Python's _strptime_ function, e.g., `%Y_%m_%d`. In YAML, use double quotes around
the string, e.g., `"%Y_%m_%d"`, to specify it is a plain YAML string.

The schedule can specify more than one FotD for a specific day, e.g., roses from
Netherlands and roses from Mexico on November 3rd, 2014.
Multiple identical entries in teh schedule are allowed and collapsed into one entry.

## Participating Ports

Ports participating in the program can be specified as a list under a key called `ports`.
For example:

```yaml
release_programs:
  cfrp:
    schedule:
      file_name: schedule.csv
    ports:
      - NY JFK CBP
      - FL Miami Air CBP
```

Only when the consignment is in one of the ports in the list, it is considered for the program.
If the consignment is in the port not in the list, it does not qualify for the program.

## Output

If the simulation is producing a F280-like text output, name of the program will appear
in the output as `cfrp` when consignment qualified for the program. To customize this name,
use, e.g., `name: CFRP` under the key `cfrp` like this:

```yaml
release_programs:
  cfrp:
    name: CFRP
```

---

Next: [Inspections](inspections.md)
