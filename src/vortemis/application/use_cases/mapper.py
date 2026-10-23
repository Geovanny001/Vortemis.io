from collections.abc import Mapping

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp


class ZeekFlowMapper:
    def to_flow(self, data: Mapping[str, str]) -> NetworkFlow | None:
        try:
            return NetworkFlow(
                src_ip=IPAddress(data["id.orig_h"]),
                dst_ip=IPAddress(data["id.resp_h"]),
                src_port=Port(int(data["id.orig_p"])),
                dst_port=Port(int(data["id.resp_p"])),
                proto=Protocol.from_raw(data["proto"]),
                ts=Timestamp.from_epoch(float(data["ts"])),
                orig_bytes=_to_int(data.get("orig_bytes")),
                resp_bytes=_to_int(data.get("resp_bytes")),
                duration=_to_float(data.get("duration")),
                conn_state=data.get("conn_state"),
            )
        except (KeyError, TypeError, ValueError, OverflowError):
            return None


def _to_int(value: str | None) -> int:
    if value is None or value == "-":
        return 0
    return int(value)


def _to_float(value: str | None) -> float:
    if value is None or value == "-":
        return 0.0
    return float(value)
