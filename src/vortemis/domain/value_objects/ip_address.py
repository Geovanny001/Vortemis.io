from dataclasses import dataclass
from ipaddress import ip_address

from vortemis.domain.errors import InvalidIPAddressError


@dataclass(frozen=True, slots=True)
class IPAddress:
    value: str

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "value", ip_address(self.value).compressed)
        except ValueError as exc:
            raise InvalidIPAddressError(f"invalid IP address: {self.value!r}") from exc

    @property
    def version(self) -> int:
        return ip_address(self.value).version
