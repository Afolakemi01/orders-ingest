# Orders Ingest: Validated CSV → Parquet Pipeline

A Python batch pipeline that turns a messy, hand-typed orders export into a typed, analytics-ready Parquet file. Every rejected row is kept in a separate file, with a reason code.

## Problem

A small UK online shop exports its daily orders as a hand-typed CSV. The file contains blank fields, impossible dates, non-numeric amounts, negative values, short rows and rows with extra values.

Two teams depend on this file:

- **Analytics** needs clean, correctly typed orders it can trust.
- **Operations** needs every rejected order, with a reason, so the problem can be fixed at the source.

## Architecture

```
data/raw/orders_raw.csv
        │
        ▼
  read_orders ──► validate (4 tiers, fixed order)
        │                 │
        │        ┌────────┴─────────┐
        ▼        ▼                  ▼
   reconcile   clean rows        rejected rows
   (read = clean + rejected)        │
                 │                  │
                 ▼                  ▼
   output/orders_clean.parquet   output/orders_rejects.csv
   (declared schema)             (reason + original values)
```

## Tech stack

| Tool | Purpose |
|---|---|
| Python | pipeline logic, using only the standard library (`csv`, `decimal`, `datetime`, `logging`, `pathlib`) |
| PyArrow | writes Parquet with an explicit schema |
| pytest | unit tests |
| Ruff | linting and formatting |
| `pyproject.toml` | one file for dependencies, packaging and tool settings |

## Validation tiers

Each tier returns `(record, reason)`. A row stops at the first tier it fails.

| Tier | Checks | Example reason code |
|---|---|---|
| 1. Fields | unexpected keys, missing keys, keys holding `None` (short rows) | `unexpected_field`, `missing_quantity` |
| 2. Blank | strips surrounding whitespace, then rejects empty values | `blank_customer_email` |
| 3. Cast | converts text to real types (`date`, `Decimal`, `int`); amounts must be finite with at most 2 decimal places | `invalid_order_date`, `invalid_amount_gbp` |
| 4. Range | business rules: `amount_gbp > 0`, `quantity >= 1` | `out_of_range_quantity` |

**Why the order is fixed:**

- Tier 1 removes `None` values, so tier 2 can safely call `.strip()`.
- Tier 2 removes blanks, so a tier 3 failure always means bad content, never missing content.
- Tier 3 produces real numbers, so tier 4 can compare them.

## Design decisions

- **Fix only what is certain; reject everything else.** Surrounding whitespace is stripped because that loses no meaning. `"1,200.00"` is rejected rather than having its comma removed, because what a comma means varies by locale.
- **No row is silently dropped.** Every row read ends up in exactly one output.
- **Reconciliation on every run.** Before anything is written, the pipeline checks that `read == clean + rejected`. A run that has lost rows stops.
- **Money uses `Decimal`, not `float`.** Amounts are stored as `decimal128(10, 2)`, so there is no floating-point rounding error. Amounts are never rounded: a value with more than two decimal places is rejected, because whether `15.123` means £15.12 or a mistyped £151.23 cannot be known.
- **Declared Parquet schema.** The column types are fixed (`string`, `date32`, `decimal128(10, 2)`, `int64`). When the module loads, the schema's column names are checked against the expected field set.
- **Rejects keep the original values**, plus an `extra` column that captures any unexpected values.
- **Capability separated from decisions.** `cleaning.py` holds reusable functions and contains no file paths or logging setup. `pipeline.py` owns the run: it reads paths from `config.json` and resolves them against the project root, so the output does not depend on the working directory.

## Error handling and logging

There are two levels of failure, and each is handled differently.

| Failure | Example | Behaviour |
|---|---|---|
| **Row-level** | invalid date, negative quantity | The row goes to the rejects file with a reason code. The run continues. |
| **Run-level** | missing input file, broken config | The failure is logged with its full traceback and then re-raised, so the process exits with a non-zero code and a scheduler sees the run as failed. |

Each run logs timestamped lines for: run start, row counts (read / clean / rejected), a `WARNING` when any row is rejected, each output file written, and run finish. At `DEBUG` level, each rejected row is also logged with its row number and reason.

## Project structure

```
orders-ingest/
├── orders_ingest/
│   ├── __init__.py
│   ├── pipeline.py        # entry point: config, paths, run steps, logging
│   └── cleaning.py        # validation, reading and writing functions
├── tests/
│   └── test_cleaning.py   # unit tests
├── data/raw/              # input CSV
├── output/                # generated Parquet and rejects CSV
├── config.json            # input and output paths
└── pyproject.toml         # dependencies, packaging, pytest and Ruff settings
```

## Setup

Tested with Python 3.14.

```bash
git clone https://github.com/Afolakemi01/orders-ingest.git
cd orders-ingest
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`-e` installs the package in editable mode, so code changes take effect without reinstalling. `[dev]` adds pytest and Ruff.

## Run

```bash
python -m orders_ingest.pipeline
```

Input and output paths are set in `config.json`.

## Sample result

13 rows read → 3 clean → 10 rejected. Reconciliation passes.

## Tests and code quality

```bash
pytest               # run the tests
ruff check .         # lint
ruff format --check .  # check formatting
```

The tests cover:

- a complete record passing the blank check, with whitespace stripped
- a valid record converted to the correct types
- an invalid quantity rejected with the reason `invalid_quantity`
- an amount with three decimal places rejected with the reason `invalid_amount_gbp`
- a `NaN` amount rejected with the reason `invalid_amount_gbp`
- a missing input file raising `FileNotFoundError`
- an amount that was never cast raising `TypeError` in the range check

Current status: 7 passing, Ruff clean.

## Known limitations

- **Reconciliation uses `assert`,** which Python disables when run with `-O`. A production version would raise an explicit exception.
- **The tier 1 reason for an absent column is generic** (`missing_field`) and does not name the column.

## Future improvements

- Replace the reconciliation `assert` with an explicit exception.
- Load clean rows into PostgreSQL alongside Parquet.
- Containerise with Docker and schedule with Airflow.
- Add a GitHub Actions check that runs the tests and Ruff on every push.

