from datetime import date

import pytest

from orders_ingest.cleaning import check_blank, check_cast, check_range, read_orders


def test_check_blank_accepts_a_complete_record():
    record = {
        "order_id": " A1 ",
        "customer_email": "Ada@uk.com ",
        "order_date": "2026-08-01",
        "amount_gbp": "15",
        "quantity": " 20",
    }
    cleaned, reason = check_blank(record)
    assert reason is None
    assert cleaned["order_id"] == "A1"


def test_check_cast_converts_a_valid_record():
    record = {
        "order_id": "A1",
        "customer_email": "ada@uk.com",
        "order_date": "2026-08-01",
        "amount_gbp": "15",
        "quantity": "20",
    }

    typed, reason = check_cast(record)

    assert reason is None
    assert typed["order_date"] == date(2026, 8, 1)
    assert typed["quantity"] == 20


def test_check_cast_rejects_invalid_quantity():
    record = {
        "order_id": "A1",
        "customer_email": "ada@uk.com",
        "order_date": "2026-08-01",
        "amount_gbp": "15",
        "quantity": "abc",
    }

    reject, reason = check_cast(record)
    assert reason == "invalid_quantity"
    assert reject["quantity"] == "abc"


def test_check_cast_rejects_three_decimal_places():
    record = {
        "order_id": "A1",
        "customer_email": "ada@uk.com",
        "order_date": "2026-08-01",
        "amount_gbp": "15.123",
        "quantity": "5",
    }

    reject, reason = check_cast(record)
    assert reason == "invalid_amount_gbp"
    assert reject["amount_gbp"] == "15.123"


def test_check_cast_rejects_nan_amount():
    record = {
        "order_id": "A1",
        "customer_email": "ada@uk.com",
        "order_date": "2026-08-01",
        "amount_gbp": "NaN",
        "quantity": "5",
    }
    reject, reason = check_cast(record)
    assert reason == "invalid_amount_gbp"
    assert reject["amount_gbp"] == "NaN"


def test_check_range_rejects_invalid_gbp():
    record = {
        "order_id": "A1",
        "customer_email": "ada@uk.com",
        "order_date": "2026-08-01",
        "amount_gbp": "0",
        "quantity": "abc",
    }
    with pytest.raises(TypeError):
        check_range(record)


def test_read_file_rejects_invalid_file():
    path = "does_not_exist.csv"
    with pytest.raises(FileNotFoundError):
        read_orders(path)
