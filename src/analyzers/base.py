"""Base interface for deterministic static analyzers."""

from abc import ABC, abstractmethod
from typing import Sequence
from src.schemas import Finding


class BaseAnalyzer(ABC):
    """Abstract base class for all deterministic code analyzers."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the analyzer binary or library is available in the current environment."""
        pass

    @abstractmethod
    def run(self, file_paths: Sequence[str]) -> list[Finding]:
        """Execute analyzer against provided file paths and return normalized findings."""
        pass
