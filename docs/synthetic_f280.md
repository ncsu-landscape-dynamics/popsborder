# Obtaining synthetic F280 records

## Configuring disposition codes

Here is an example with disposition codes close to what is used in F280:

```
disposition_codes:
  inspected_ok: IRMR
  inspected_pest: FUAP
  cfrp_inspected_ok: IRAR
  cfrp_inspected_pest: FUAR
  cfrp_not_inspected: REAR
```

## Generating a synthetic dataset

Generating a synthetic dataset with F280 records only can be done using
the following wrapper script included in the repository:

```
./generate_synthetic_F280_dataset.sh synthetic_records.csv 1000
```

## Obtaining a pre-computed sample dataset

### Download using a web browser

To download sample synthetic database records (F280)
by clicking [this link](https://ncsu-landscape-dynamics.github.io/popsborder/synthetic_records.csv).

### Download using command line

Alternatively, in a Linux command line (or in an equivalent environment),
you can execute (assuming you have `wget` installed):

```
wget https://ncsu-landscape-dynamics.github.io/popsborder/synthetic_records.csv
ls synthetic_records.csv
```

The last command (`ls`) just confirms that you have the data downloaded
and uncompressed. If you need some troubleshooting,
the following example might be helpful (relying of the program `file`).

```
$ file synthetic_records.csv
synthetic_records.csv: ASCII text
```
