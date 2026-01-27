"""Playwright report handler."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from ..base import ReportHandler
from ..models import (
    ExtractedReport,
    NormalizedReport,
    ReportType,
    TestCase,
    TestStatus,
    TestSuite,
)


class PlaywrightHandler(ReportHandler):
    """Handler for Playwright test reports.

    Supports both JSON format (report.json) and HTML format
    (index.html + data/ directory).
    """

    @property
    def name(self) -> str:
        """Return the framework name."""
        return "playwright"

    def can_handle(self, zip_file: ZipFile) -> bool:
        """Check if this is a Playwright report.

        Playwright reports can be identified by:
        - JSON: Contains report.json with 'suites' and 'config' keys
        - HTML: Contains index.html and data/ directory
        """
        namelist = zip_file.namelist()

        # Check for HTML report structure
        if self._is_html_report(namelist):
            return True

        # Check for JSON report
        if self._is_json_report(zip_file, namelist):
            return True

        return False

    def _is_html_report(self, namelist: list[str]) -> bool:
        """Check if ZIP contains Playwright HTML report structure."""
        has_index = any(name == "index.html" or name.endswith("/index.html") for name in namelist)
        has_data = any(name.startswith("data/") or "/data/" in name for name in namelist)
        return has_index and has_data

    def _is_json_report(self, zip_file: ZipFile, namelist: list[str]) -> bool:
        """Check if ZIP contains Playwright JSON report."""
        json_files = [n for n in namelist if n.endswith(".json")]

        for json_file in json_files:
            try:
                content = zip_file.read(json_file)
                data = json.loads(content)
                if self._is_playwright_json_structure(data):
                    return True
            except (json.JSONDecodeError, KeyError):
                continue

        return False

    def _is_playwright_json_structure(self, data: dict) -> bool:
        """Check if JSON has Playwright report structure."""
        # Playwright reports have 'suites' or 'config' at top level
        if isinstance(data, dict):
            if "suites" in data or ("config" in data and "suites" in data):
                return True
            # Also check for stats which is common in Playwright
            if "stats" in data and any(
                k in data.get("stats", {}) for k in ["expected", "unexpected", "flaky", "skipped"]
            ):
                return True
        return False

    def extract(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract Playwright report to output directory."""
        namelist = zip_file.namelist()

        if self._is_html_report(namelist):
            return self._extract_html_report(zip_file, output_dir)
        else:
            return self._extract_json_report(zip_file, output_dir)

    def _extract_json_report(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract JSON format report."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find and extract the JSON report file
        json_file = self._find_json_report_file(zip_file)
        if not json_file:
            raise ValueError("Could not find Playwright JSON report in ZIP")

        content = zip_file.read(json_file)
        data = json.loads(content)

        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(data, indent=2))

        return ExtractedReport(
            report_type=ReportType.JSON,
            root_dir=output_dir,
            data_file=report_path,
            entry_point=report_path,
            raw_data=data,
        )

    def _extract_html_report(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract HTML format report."""
        html_dir = output_dir / "html_report"
        html_dir.mkdir(parents=True, exist_ok=True)

        # Extract all files preserving directory structure
        for name in zip_file.namelist():
            if name.endswith("/"):
                (html_dir / name).mkdir(parents=True, exist_ok=True)
            else:
                target_path = html_dir / name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_bytes(zip_file.read(name))

        # Find the entry point (index.html)
        entry_point = html_dir / "index.html"
        if not entry_point.exists():
            # Try to find it in subdirectories
            for html_file in html_dir.rglob("index.html"):
                entry_point = html_file
                break

        # For HTML reports, we need to extract JSON data from data/ directory
        # The data files contain the actual test results
        data_file = self._extract_data_from_html_report(html_dir, output_dir)

        return ExtractedReport(
            report_type=ReportType.HTML,
            root_dir=html_dir,
            data_file=data_file,
            entry_point=entry_point,
            raw_data=None,  # Will be loaded during normalize
        )

    def _extract_data_from_html_report(self, html_dir: Path, output_dir: Path) -> Path:
        """Extract JSON data from HTML report's data directory.

        Playwright HTML reports store test data in data/*.zip files.
        We need to extract and combine them.
        """
        data_dir = html_dir / "data"
        combined_data: dict = {"suites": [], "stats": {}}

        if data_dir.exists():
            import zipfile

            for data_file in data_dir.glob("*.zip"):
                try:
                    with zipfile.ZipFile(data_file) as inner_zip:
                        for name in inner_zip.namelist():
                            if name.endswith(".json"):
                                content = inner_zip.read(name)
                                data = json.loads(content)
                                # Merge suite data
                                if "suites" in data:
                                    combined_data["suites"].extend(data["suites"])
                                if "stats" in data:
                                    for k, v in data["stats"].items():
                                        combined_data["stats"][k] = (
                                            combined_data["stats"].get(k, 0) + v
                                        )
                except (zipfile.BadZipFile, json.JSONDecodeError):
                    continue

        # Save combined data
        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(combined_data, indent=2))

        return report_path

    def _find_json_report_file(self, zip_file: ZipFile) -> str | None:
        """Find the main JSON report file in the ZIP."""
        namelist = zip_file.namelist()

        # Priority order for finding the report
        candidates = [
            "report.json",
            "playwright-report.json",
            "results.json",
        ]

        for candidate in candidates:
            if candidate in namelist:
                return candidate

        # Fall back to any JSON file that looks like a Playwright report
        for name in namelist:
            if name.endswith(".json"):
                try:
                    content = zip_file.read(name)
                    data = json.loads(content)
                    if self._is_playwright_json_structure(data):
                        return name
                except (json.JSONDecodeError, KeyError):
                    continue

        return None

    def normalize(self, extracted: ExtractedReport) -> NormalizedReport:
        """Convert Playwright report to normalized format."""
        # Load data if not already loaded
        if extracted.raw_data:
            data = extracted.raw_data
        else:
            data = json.loads(extracted.data_file.read_text())

        suites = self._normalize_suites(data.get("suites", []))
        stats = data.get("stats", {})

        # Calculate totals
        passed = stats.get("expected", 0)
        failed = stats.get("unexpected", 0) + stats.get("flaky", 0)
        skipped = stats.get("skipped", 0)
        total = passed + failed + skipped

        return NormalizedReport(
            framework="playwright",
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            skipped_tests=skipped,
            suites=suites,
            raw_report=data,
        )

    def _normalize_suites(self, suites: list[dict]) -> list[TestSuite]:
        """Convert Playwright suites to normalized TestSuite objects."""
        result = []

        for suite in suites:
            tests = []
            nested_suites = []

            # Process specs (test files in Playwright)
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    test_case = self._normalize_test(test, spec)
                    tests.append(test_case)

            # Process nested suites
            if "suites" in suite:
                nested_suites = self._normalize_suites(suite["suites"])

            result.append(
                TestSuite(
                    name=suite.get("title", "Unknown Suite"),
                    tests=tests,
                    suites=nested_suites,
                    file_path=suite.get("file"),
                )
            )

        return result

    def _normalize_test(self, test: dict, spec: dict) -> TestCase:
        """Convert a Playwright test to normalized TestCase."""
        # Get the last result (most recent run)
        results = test.get("results", [])
        last_result = results[-1] if results else {}

        status_str = last_result.get("status", test.get("status", "passed"))
        status = self._map_status(status_str)

        error_message = None
        error_stack = None

        if status == TestStatus.FAILED:
            errors = last_result.get("errors", [])
            if errors:
                error_message = errors[0].get("message", "")
                error_stack = errors[0].get("stack", "")

        return TestCase(
            name=spec.get("title", test.get("title", "Unknown Test")),
            status=status,
            duration_ms=last_result.get("duration"),
            error_message=error_message,
            error_stack=error_stack,
            file_path=spec.get("file"),
            line_number=spec.get("line"),
        )

    def _map_status(self, status: str) -> TestStatus:
        """Map Playwright status to normalized TestStatus."""
        status_map = {
            "passed": TestStatus.PASSED,
            "expected": TestStatus.PASSED,
            "failed": TestStatus.FAILED,
            "unexpected": TestStatus.FAILED,
            "flaky": TestStatus.FAILED,
            "skipped": TestStatus.SKIPPED,
            "timedOut": TestStatus.FAILED,
            "interrupted": TestStatus.FAILED,
        }
        return status_map.get(status, TestStatus.FAILED)
