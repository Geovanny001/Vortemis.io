from vortemis.application.use_cases.mapper import ZeekFlowMapper

_ROW = {
    "ts": "1700000000.000000",
    "uid": "C1",
    "id.orig_h": "192.168.1.10",
    "id.orig_p": "50000",
    "id.resp_h": "10.0.0.5",
    "id.resp_p": "443",
    "proto": "tcp",
    "duration": "1.5",
    "orig_bytes": "100",
    "resp_bytes": "200",
    "conn_state": "SF",
}


def test_mapper_assigns_a_deterministic_flow_id() -> None:
    mapper = ZeekFlowMapper()

    first = mapper.to_flow(_ROW)
    second = mapper.to_flow(_ROW)

    assert first is not None
    assert second is not None
    assert first.flow_id == second.flow_id


def test_mapper_flow_id_changes_with_timestamp() -> None:
    mapper = ZeekFlowMapper()

    first = mapper.to_flow(_ROW)
    second = mapper.to_flow({**_ROW, "ts": "1700000001.000000"})

    assert first is not None
    assert second is not None
    assert first.flow_id != second.flow_id


def test_mapper_returns_none_for_invalid_rows() -> None:
    mapper = ZeekFlowMapper()

    assert mapper.to_flow({**_ROW, "id.orig_h": "999.999.999.999"}) is None
    assert mapper.to_flow({**_ROW, "id.orig_p": "70000"}) is None
