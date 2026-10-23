from dataclasses import dataclass
from datetime import UTC, datetime

from vortemis.domain.errors import InvalidTimestampError


@dataclass(frozen=True, slots=True)
class Timestamp:
    value: datetime

    def __post_init__(self) -> None:
        if self.value.tzinfo is None or self.value.tzinfo.utcoffset(self.value) is None:
            raise InvalidTimestampError("timestamp must be timezone-aware")
        object.__setattr__(self, "value", self.value.astimezone(UTC))

    @classmethod
    def from_epoch(cls, epoch: float) -> Timestamp:
        return cls(datetime.fromtimestamp(epoch, tz=UTC))
