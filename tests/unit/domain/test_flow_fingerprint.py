from vortemis.domain.value_objects.flow_fingerprint import flow_fingerprint

_BASE = {
    "ts": 1_700_000_000.123456,
    "src_ip": "192.168.1.10",
    "src_port": 50000,
    "dst_ip": "10.0.0.5",
    "dst_port": 443,
    "protocol": "tcp",
}


def test_fingerprint_is_stable_for_the_same_flow() -> None:
    assert flow_fingerprint(**_BASE) == flow_fingerprint(**_BASE)


def test_fingerprint_changes_with_timestamp() -> None:
    other = {**_BASE, "ts": 1_700_000_001.123456}

    assert flow_fingerprint(**_BASE) != flow_fingerprint(**other)


def test_fingerprint_changes_with_endpoints_and_protocol() -> None:
    fingerprints = {
        flow_fingerprint(**_BASE),
        flow_fingerprint(**{**_BASE, "src_ip": "192.168.1.11"}),
        flow_fingerprint(**{**_BASE, "dst_ip": "10.0.0.6"}),
        flow_fingerprint(**{**_BASE, "src_port": 50001}),
        flow_fingerprint(**{**_BASE, "dst_port": 80}),
        flow_fingerprint(**{**_BASE, "protocol": "udp"}),
    }

    assert len(fingerprints) == 6
