import ipaddress
from datetime import date


def validate_ip_filter(value: str) -> str | None:
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return None
    except ValueError:
        pass
    try:
        ipaddress.ip_network(value, strict=False)
        return None
    except ValueError:
        return "Invalid IPv4/IPv6 address format"


def validate_port_filter(value: str) -> str | None:
    if value in ("", None):
        return None
    try:
        port = int(value)
    except ValueError:
        return "Port must be an integer between 1 and 65535"
    if not 1 <= port <= 65535:
        return "Port must be between 1 and 65535"
    return None


def validate_date_range(start: date | None, end: date | None) -> str | None:
    if start is not None and end is not None and start > end:
        return "Start date cannot be after end date"
    return None
