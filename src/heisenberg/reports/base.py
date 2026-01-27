"""Abstract base class for report handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from zipfile import ZipFile

from .models import ExtractedReport, NormalizedReport


class ReportHandler(ABC):
    """Abstract base class for test report handlers.

    Each test framework (Playwright, Jest, Cypress, etc.) should have
    a concrete implementation of this class.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the framework this handler supports."""

    @abstractmethod
    def can_handle(self, zip_file: ZipFile) -> bool:
        """Check if this handler can process the given ZIP file.

        Args:
            zip_file: An open ZipFile object to inspect.

        Returns:
            True if this handler recognizes the report format.
        """

    @abstractmethod
    def extract(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract the report from the ZIP file to the output directory.

        Args:
            zip_file: An open ZipFile object to extract from.
            output_dir: Directory to extract files to.

        Returns:
            ExtractedReport with paths to extracted files.
        """

    @abstractmethod
    def normalize(self, extracted: ExtractedReport) -> NormalizedReport:
        """Convert the extracted report to a normalized format.

        Args:
            extracted: The extracted report to normalize.

        Returns:
            NormalizedReport in the common format for AI analysis.
        """
