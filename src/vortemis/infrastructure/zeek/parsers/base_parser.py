from abc import ABC, abstractmethod


class BaseParser(ABC):
    @abstractmethod
    def parse_line(self, line: str) -> dict[str, str]:
        ...
