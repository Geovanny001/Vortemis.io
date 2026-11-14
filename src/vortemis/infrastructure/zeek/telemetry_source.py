import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import aiofiles

from vortemis.application.ports.driving.raw_record import RawRecord
from vortemis.infrastructure.zeek.parsers.base_parser import BaseParser
from vortemis.infrastructure.zeek.parsers.json_parser import JsonParser
from vortemis.infrastructure.zeek.parsers.tsv_parser import TsvParser

_POLL_INTERVAL = 1.5


def _file_state(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size)


class ZeekTelemetrySource:
    def __init__(
        self,
        file_path: Path,
        follow: bool = False,
        start_offset: int = 0,
    ) -> None:
        self._file_path = file_path
        self._follow = follow
        self._start_offset = start_offset
        self._position = start_offset
        self._parser = self._select_parser(file_path)

    @property
    def position(self) -> int:
        return self._position

    def _select_parser(self, file_path: Path) -> BaseParser:
        if file_path.suffix == ".json":
            return JsonParser()
        return TsvParser()

    async def stream(self) -> AsyncIterator[RawRecord]:
        while True:
            rotated = False
            async with aiofiles.open(self._file_path, "rb") as handle:
                if self._start_offset:
                    while True:
                        header_line = await handle.readline()
                        if header_line == b"":
                            break
                        decoded = header_line.decode("utf-8", errors="replace")
                        if not decoded.startswith("#"):
                            break
                        self._parser.parse_line(decoded.rstrip("\r\n"))
                    await handle.seek(self._start_offset)
                identity = (await asyncio.to_thread(_file_state, self._file_path))[:2]
                source_line = 0
                while True:
                    read_position = await handle.tell()
                    raw_line = await handle.readline()
                    if raw_line == b"":
                        self._position = await handle.tell()
                        if not self._follow:
                            break
                        state = await asyncio.to_thread(_file_state, self._file_path)
                        if state[:2] != identity:
                            rotated = True
                            break
                        if state[2] < self._position:
                            await handle.seek(0)
                            self._position = 0
                            continue
                        await asyncio.sleep(_POLL_INTERVAL)
                        continue
                    line = raw_line.decode("utf-8", errors="replace")
                    if not line.endswith("\n") and self._follow:
                        await handle.seek(read_position)
                        self._position = read_position
                        await asyncio.sleep(_POLL_INTERVAL)
                        continue
                    source_line += 1
                    self._position = await handle.tell()
                    cleaned = line.rstrip("\r\n")
                    if not cleaned:
                        continue
                    data = self._parser.parse_line(cleaned)
                    if not data:
                        continue
                    yield RawRecord(data=data, source_line=source_line)
            if not rotated:
                break
            self._start_offset = 0
            self._position = 0
            await asyncio.sleep(_POLL_INTERVAL)
