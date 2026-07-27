"""Extractor protocol for single-blob file types (pdf, image, text). CSV is separate."""

from pathlib import Path
from typing import Protocol


class Extractor(Protocol):
    def extract(self, path: Path) -> str: ...
