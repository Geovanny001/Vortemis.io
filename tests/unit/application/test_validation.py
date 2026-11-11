from datetime import date

from vortemis.application.validation import (
    validate_date_range,
    validate_ip_filter,
    validate_port_filter,
)


def test_validate_ip_filter_accepts_address_and_cidr() -> None:
    assert validate_ip_filter("192.168.1.10") is None
    assert validate_ip_filter("10.0.0.0/8") is None
    assert validate_ip_filter("::1") is None


def test_validate_ip_filter_rejects_garbage() -> None:
    error = validate_ip_filter("not-an-ip")
    assert error is not None
    assert validate_ip_filter("") is None


def test_validate_port_filter_enforces_bounds() -> None:
    assert validate_port_filter("443") is None
    assert validate_port_filter("0") is not None
    assert validate_port_filter("70000") is not None
    assert validate_port_filter("abc") is not None
    assert validate_port_filter("") is None


def test_validate_date_range_rejects_reversed() -> None:
    assert validate_date_range(date(2026, 1, 1), date(2026, 1, 31)) is None
    assert validate_date_range(date(2026, 2, 1), date(2026, 1, 1)) is not None
    assert validate_date_range(None, date(2026, 1, 1)) is None
