from datetime import UTC, datetime, timedelta, timezone

import pytest

from vortemis.domain.errors import (
    DomainValidationError,
    InvalidIPAddressError,
    InvalidPortError,
    InvalidTimestampError,
)
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp


def test_ipv4_address_is_parsed_and_reports_version_four() -> None:
    ip = IPAddress("192.168.1.1")
    assert ip.value == "192.168.1.1"
    assert ip.version == 4


def test_ipv6_address_is_parsed_and_reports_version_six() -> None:
    ip = IPAddress("2001:db8::1")
    assert ip.value == "2001:db8::1"
    assert ip.version == 6


def test_ip_address_is_normalized_to_canonical_form() -> None:
    assert IPAddress("2001:0db8:0000:0000:0000:0000:0000:0001").value == "2001:db8::1"


def test_invalid_ip_address_raises() -> None:
    with pytest.raises(InvalidIPAddressError):
        IPAddress("999.999.999.999")


def test_malformed_ip_address_raises() -> None:
    with pytest.raises(InvalidIPAddressError):
        IPAddress("not-an-ip")


def test_port_accepts_boundaries() -> None:
    assert Port(1).value == 1
    assert Port(65535).value == 65535
    assert Port(443).value == 443


def test_port_below_range_raises() -> None:
    with pytest.raises(InvalidPortError):
        Port(0)


def test_port_above_range_raises() -> None:
    with pytest.raises(InvalidPortError):
        Port(65536)


def test_port_negative_raises() -> None:
    with pytest.raises(InvalidPortError):
        Port(-1)


def test_protocol_from_raw_is_case_insensitive() -> None:
    assert Protocol.from_raw("TCP") is Protocol.TCP
    assert Protocol.from_raw("udp") is Protocol.UDP


def test_protocol_from_raw_strips_whitespace() -> None:
    assert Protocol.from_raw("  icmp  ") is Protocol.ICMP


def test_protocol_from_raw_unknown_raises() -> None:
    with pytest.raises(DomainValidationError):
        Protocol.from_raw("sctp")


def test_timestamp_requires_timezone_aware_datetime() -> None:
    with pytest.raises(InvalidTimestampError):
        Timestamp(datetime(2024, 1, 1, 12, 0, 0))


def test_timestamp_normalizes_non_utc_to_utc() -> None:
    offset = timezone(timedelta(hours=2))
    value = Timestamp(datetime(2024, 1, 1, 14, 0, 0, tzinfo=offset))
    assert value.value == datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_timestamp_from_epoch_produces_utc() -> None:
    value = Timestamp.from_epoch(0.0)
    assert value.value == datetime(1970, 1, 1, tzinfo=UTC)
