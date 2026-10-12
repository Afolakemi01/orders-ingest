import csv
import logging
from datetime import date
from decimal import Decimal, InvalidOperation

import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)

EXPECTED = {"order_id", "customer_email", "order_date", "amount_gbp", "quantity"}
SCHEMA = pa.schema(
    [
        ("order_id", pa.string()),
        ("customer_email", pa.string()),
        ("order_date", pa.date32()),
        ("amount_gbp", pa.decimal128(10, 2)),
        ("quantity", pa.int64()),
    ]
)

assert set(SCHEMA.names) == EXPECTED, "schema names do not match EXPECTED"


def check_fields(record):
    keys = set(record)
    missing = EXPECTED - keys
    unexpected = keys - EXPECTED

    if unexpected:
        return (record, "unexpected_field")

    if missing:
        return (record, "missing_field")

    for field in sorted(EXPECTED):
        if record[field] is None:
            return (record, f"missing_{field}")

    return (record, None)


def check_blank(record):
    cleaned = {key: value.strip() for key, value in record.items()}

    for field in sorted(EXPECTED):
        if cleaned[field] == "":
            return (cleaned, f"blank_{field}")

    return (cleaned, None)


def check_cast(record):
    try:
        order_date = date.fromisoformat(record["order_date"])
    except ValueError:
        return (record, "invalid_order_date")

    try:
        amount = Decimal(record["amount_gbp"])
    except InvalidOperation:
        return (record, "invalid_amount_gbp")

    if not amount.is_finite():
        return (record, "invalid_amount_gbp")

    if amount != amount.quantize(Decimal("0.01")):
        return (record, "invalid_amount_gbp")

    try:
        quantity = int(record["quantity"])
    except ValueError:
        return (record, "invalid_quantity")

    typed = {
        "order_id": record["order_id"],
        "customer_email": record["customer_email"],
        "order_date": order_date,
        "amount_gbp": amount,
        "quantity": quantity,
    }

    return (typed, None)


def check_range(record):
    if record["amount_gbp"] <= 0:
        return (record, "out_of_range_amount_gbp")

    if record["quantity"] < 1:
        return (record, "out_of_range_quantity")

    return (record, None)


def validate(record):
    record, reason = check_fields(record)
    if reason is not None:
        return (record, reason)

    record, reason = check_blank(record)
    if reason is not None:
        return (record, reason)

    record, reason = check_cast(record)
    if reason is not None:
        return (record, reason)

    record, reason = check_range(record)
    if reason is not None:
        return (record, reason)

    return (record, None)


def read_orders(path):
    clean = []
    rejects = []
    read_count = 0

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            read_count += 1
            record, reason = validate(row)

            if reason is not None:
                rejects.append({"reason": reason, "raw": row})
                logger.debug("row: %s rejected: %s", read_count, reason)
            else:
                clean.append(record)

    assert read_count == len(clean) + len(rejects), (
        f"counts do not match: read={read_count}, clean={len(clean)}, rejects={len(rejects)}"
    )
    return (clean, rejects, read_count)


def write_clean(records, path):
    table = pa.Table.from_pylist(records, schema=SCHEMA)
    pq.write_table(table, path)
    return table.num_rows


def write_reject(rejects, path):
    fieldnames = [
        "reason",
        "order_id",
        "customer_email",
        "order_date",
        "amount_gbp",
        "quantity",
        "extra",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        reject_writer = csv.DictWriter(f, fieldnames=fieldnames)

        reject_writer.writeheader()
        for item in rejects:
            reject_writer.writerow(
                {
                    "reason": item["reason"],
                    "order_id": item["raw"].get("order_id"),
                    "customer_email": item["raw"].get("customer_email"),
                    "order_date": item["raw"].get("order_date"),
                    "amount_gbp": item["raw"].get("amount_gbp"),
                    "quantity": item["raw"].get("quantity"),
                    "extra": item["raw"].get(None),
                }
            )
    return len(rejects)


if __name__ == "__main__":
    print("cleaning.py is a module; run pipeline.py instead")
