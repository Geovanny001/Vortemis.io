from datetime import UTC, datetime

import pytest

from vortemis.application.queries.filters import FlowFilters


def test_filters_normalize_protocol_and_tactic() -> None:
    filters = FlowFilters(protocol=" UDP ", tactic=" ta0010 ")

    assert filters.protocol == "udp"
    assert filters.tactic == "TA0010"


def test_filters_reject_naive_timestamps() -> None:
    with pytest.raises(ValueError):
        FlowFilters(since=datetime(2026, 11, 14))


def test_filters_reject_inverted_window() -> None:
    since = datetime(2026, 11, 14, 12, tzinfo=UTC)
    until = datetime(2026, 11, 14, 11, tzinfo=UTC)

    with pytest.raises(ValueError):
        FlowFilters(since=since, until=until)


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_filters_reject_invalid_ports(port: int) -> None:
    with pytest.raises(ValueError):
        FlowFilters(src_port=port)


@pytest.mark.parametrize("probability", [-0.1, 1.1])
def test_filters_reject_invalid_probability(probability: float) -> None:
    with pytest.raises(ValueError):
        FlowFilters(min_probability=probability)


def test_filters_accept_a_valid_combination() -> None:
    filters = FlowFilters(
        since=datetime(2026, 11, 14, 10, tzinfo=UTC),
        until=datetime(2026, 11, 14, 12, tzinfo=UTC),
        src_ip="192.168.1.10",
        dst_port=443,
        protocol="tcp",
        tactic="TA0010",
        min_probability=0.7,
    )

    assert filters.dst_port == 443
    assert filters.min_probability == 0.7
