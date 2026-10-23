from dataclasses import dataclass

from vortemis.domain.errors import InvalidPortError

MIN_PORT = 1
MAX_PORT = 65535


@dataclass(frozen=True, slots=True)
class Port:
    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise InvalidPortError(f"port must be an integer, got {self.value!r}")
        if not MIN_PORT <= self.value <= MAX_PORT:
            raise InvalidPortError(
                f"port must be within [{MIN_PORT}, {MAX_PORT}], got {self.value}"
            )
