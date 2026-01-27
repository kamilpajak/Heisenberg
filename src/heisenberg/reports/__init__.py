"""Framework-agnostic test report handling.

This module provides a unified interface for processing test reports
from different frameworks (Playwright, Jest, Cypress, etc.).

Usage:
    from heisenberg.reports import get_default_registry

    registry = get_default_registry()
    handler = registry.identify(zip_content)
    if handler:
        extracted = handler.extract(zip_file, output_dir)
        normalized = handler.normalize(extracted)
"""

from .base import ReportHandler
from .models import (
    ExtractedReport,
    NormalizedReport,
    ReportType,
    TestCase,
    TestStatus,
    TestSuite,
)
from .registry import ReportRegistry, get_default_registry

__all__ = [
    "ReportHandler",
    "ReportRegistry",
    "get_default_registry",
    "ExtractedReport",
    "NormalizedReport",
    "ReportType",
    "TestCase",
    "TestStatus",
    "TestSuite",
]
