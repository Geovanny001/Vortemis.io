import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles

from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.infrastructure.zeek.parsers.base_parser import BaseParser
from vortemis.infrastructure.zeek.parsers.json_parser import JsonParser
from vortemis.infrastructure.zeek.parsers.tsv_parser import TsvParser

_POLL_INTERVAL = 1.5


class ZeekTelemetrySource:
    def __init__(self, file_path: Path, follow: bool = False) -> None:
        self._file_path = file_path
        self._follow = follow
        self._parser = self._select_parser(file_path)

    def _select_parser(self, file_path: Path) -> BaseParser:
        if file_path.suffix == ".json":
            return JsonParser()
        return TsvParser()

    async def stream(self) -> AsyncIterator[RawRecord]:
        async with aiofiles.open(self._file_path) as handle:
            source_line = 0
            while True:
                position = await handle.tell()
                line = await handle.readline()
                if line == "":
                    if not self._follow:
                        break
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                if not line.endswith("\n") and self._follow:
                    await handle.seek(position)
                    await asyncio.sleep(_POLL_INTERVAL)
                    continue
                source_line += 1
                cleaned = line.rstrip("\r\n")
                if not cleaned:
                    continue
                data = self._parser.parse_line(cleaned)
                if not data:
                    continue
                yield RawRecord(data=data, source_line=source_line)
