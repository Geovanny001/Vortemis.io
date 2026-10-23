from vortemis.infrastructure.zeek.parsers.base_parser import BaseParser

_FIELDS_PREFIX = "#fields"


class TsvParser(BaseParser):
    def __init__(self) -> None:
        self._fields: list[str] = []

    def parse_line(self, line: str) -> dict[str, str]:
        if line.startswith("#"):
            self._capture_fields(line)
            return {}
        if not self._fields:
            return {}
        return dict(zip(self._fields, line.split("\t"), strict=False))

    def _capture_fields(self, line: str) -> None:
        if line.startswith(_FIELDS_PREFIX):
            self._fields = line.split("\t")[1:]
