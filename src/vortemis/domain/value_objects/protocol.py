from enum import StrEnum

from vortemis.domain.errors import DomainValidationError


class Protocol(StrEnum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"

    @classmethod
    def from_raw(cls, raw: str) -> Protocol:
        try:
            return cls(raw.strip().lower())
        except ValueError as exc:
            raise DomainValidationError(f"unknown protocol: {raw!r}") from exc
