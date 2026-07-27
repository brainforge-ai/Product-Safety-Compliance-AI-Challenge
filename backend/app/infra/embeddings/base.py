"""Base class for text encoders used by the embedding matcher."""

from abc import ABC, abstractmethod


class Encoder(ABC):
    @abstractmethod
    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input string."""
