from dataclasses import dataclass
from datetime import datetime

MIN_PORT = 1
MAX_PORT = 65535
MIN_PROBABILITY = 0.0
MAX_PROBABILITY = 1.0


@dataclass(frozen=True, slots=True)
class FlowFilters:
    since: datetime | None = None
    until: datetime | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    protocol: str | None = None
    tactic: str | None = None
    min_probability: float | None = None

    def __post_init__(self) -> None:
        for label, value in (("since", self.since), ("until", self.until)):
            if value is not None and value.tzinfo is None:
                raise ValueError(f"{label} must be timezone-aware")
        if (
            self.since is not None
            and self.until is not None
            and self.since > self.until
        ):
            raise ValueError("since cannot be after until")
        for label, port in (("src_port", self.src_port), ("dst_port", self.dst_port)):
            if port is not None and not MIN_PORT <= port <= MAX_PORT:
                raise ValueError(f"{label} must be within [{MIN_PORT}, {MAX_PORT}]")
        if (
            self.min_probability is not None
            and not MIN_PROBABILITY <= self.min_probability <= MAX_PROBABILITY
        ):
            raise ValueError(
                "min_probability must be within "
                f"[{MIN_PROBABILITY}, {MAX_PROBABILITY}]"
            )
        if self.protocol is not None:
            object.__setattr__(self, "protocol", self.protocol.strip().lower())
        if self.tactic is not None:
            object.__setattr__(self, "tactic", self.tactic.strip().upper())
