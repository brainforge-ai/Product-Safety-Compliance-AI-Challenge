"""Base class for single-blob file extractors (PDF, image, text). CSV is separate."""

from abc import ABC, abstractmethod
from pathlib import Path


class Extractor(ABC):
    @abstractmethod
    def extract(self, path: Path) -> str:
        """Return the full text content extracted from a file."""
