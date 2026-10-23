from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles

from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.infrastructure.zeek.parsers.base_parser import BaseParser
from vortemis.infrastructure.zeek.parsers.json_parser import JsonParser
from vortemis.infrastructure.zeek.parsers.tsv_parser import TsvParser


class ZeekTelemetrySource:
    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._parser = self._select_parser(file_path)

    def _select_parser(self, file_path: Path) -> BaseParser:
        if file_path.suffix == ".json":
            return JsonParser()
        return TsvParser()

    async def stream(self) -> AsyncIterator[RawRecord]:
        async with aiofiles.open(self._file_path) as handle:
            source_line = 0
            async for raw_line in handle:
                source_line += 1
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                data = self._parser.parse_line(line)
                if not data:
                    continue
                yield RawRecord(data=data, source_line=source_line)
