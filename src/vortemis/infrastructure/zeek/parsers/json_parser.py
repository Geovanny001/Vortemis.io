import json

from vortemis.infrastructure.zeek.parsers.base_parser import BaseParser


class JsonParser(BaseParser):
    def parse_line(self, line: str) -> dict[str, str]:
        payload = json.loads(line)
        if not isinstance(payload, dict):
            return {}
        return {str(key): str(value) for key, value in payload.items()}
