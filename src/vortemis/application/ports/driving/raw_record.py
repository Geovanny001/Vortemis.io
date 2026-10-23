from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RawRecord:
    data: dict[str, str]
    source_line: int
