from uuid import NAMESPACE_URL, UUID, uuid5

_PREFIX = "vortemis-network-flow"


def flow_fingerprint(
    *,
    ts: float,
    src_ip: str,
    src_port: int,
    dst_ip: str,
    dst_port: int,
    protocol: str,
) -> UUID:
    key = ":".join(
        [
            _PREFIX,
            protocol,
            src_ip,
            str(src_port),
            dst_ip,
            str(dst_port),
            f"{ts:.6f}",
        ]
    )
    return uuid5(NAMESPACE_URL, key)
