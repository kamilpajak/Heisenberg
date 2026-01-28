"""Playwright report handler."""

from __future__ import annotations

import io
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

# Constants for file names and extensions
INDEX_HTML = "index.html"
REPORT_JSON = "report.json"
JSON_EXT = ".json"


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
        - Blob: Contains .zip files (sharded reports for merging)
        """
        namelist = zip_file.namelist()

        # Check for HTML report structure
        if self._is_html_report(namelist):
            return True

        # Check for blob report (must be before JSON check)
        if self._is_blob_report(namelist):
            return True

        # Check for JSON report
        if self._is_json_report(zip_file, namelist):
            return True

        return False

    def _find_report_root(self, namelist: list[str]) -> str | None:
        """Find directory prefix containing a valid Playwright report.

        GitHub Actions wraps artifacts in subdirectories, so we need to search
        recursively rather than only checking the root.

        Returns:
            Directory prefix (e.g., "playwright-report/") or empty string for root,
            or None if no valid report structure found.
        """
        # Look for HTML report structure (index.html + data/ sibling)
        for name in namelist:
            if name.endswith(INDEX_HTML):
                # Extract prefix: "subdir/index.html" -> "subdir/"
                prefix = name[: -len(INDEX_HTML)]
                data_dir = f"{prefix}data/"
                if any(n.startswith(data_dir) for n in namelist):
                    return prefix

        # Look for blob report structure (.zip files without index.html)
        # Group files by their parent directory
        dirs_with_zips: dict[str, list[str]] = {}
        for name in namelist:
            if name.endswith(".zip"):
                # Get parent dir: "subdir/file.zip" -> "subdir/"
                if "/" in name:
                    parent = name.rsplit("/", 1)[0] + "/"
                else:
                    parent = ""
                dirs_with_zips.setdefault(parent, []).append(name)

        # Find a directory with .zip files but no index.html
        for prefix, zips in dirs_with_zips.items():
            index_path = f"{prefix}{INDEX_HTML}" if prefix else INDEX_HTML
            if index_path not in namelist and zips:
                return prefix

        return None

    def _is_html_report(self, namelist: list[str]) -> bool:
        """Check if ZIP contains Playwright HTML report structure."""
        has_index = any(name == INDEX_HTML or name.endswith(f"/{INDEX_HTML}") for name in namelist)
        has_data = any(name.startswith("data/") or "/data/" in name for name in namelist)
        return has_index and has_data

    def _is_blob_report(self, namelist: list[str]) -> bool:
        """Check if ZIP contains Playwright blob report structure.

        Blob reports are created by --reporter=blob and contain:
        - .zip files (report-*.zip) with shard data
        - NO index.html (distinguishes from HTML reports)

        These can be merged with `npx playwright merge-reports`.
        Supports both root-level and nested blob reports.
        """
        # First, check if this is an HTML report - if so, it's not a blob
        if self._is_html_report(namelist):
            return False

        # Find directories containing .zip files (excluding data/ subdirs of HTML reports)
        # HTML reports have data/*.zip which are internal files, not blob shards
        dirs_with_zips: set[str] = set()
        for name in namelist:
            if name.endswith(".zip"):
                if "/" in name:
                    parent = name.rsplit("/", 1)[0] + "/"
                    # Skip data/ directories - these are HTML report internal files
                    if parent.endswith("data/"):
                        continue
                else:
                    parent = ""
                dirs_with_zips.add(parent)

        if not dirs_with_zips:
            return False

        # Check if any directory with .zip files has NO index.html sibling
        for prefix in dirs_with_zips:
            index_path = f"{prefix}{INDEX_HTML}" if prefix else INDEX_HTML
            if index_path not in namelist:
                return True

        return False

    def _is_json_report(self, zip_file: ZipFile, namelist: list[str]) -> bool:
        """Check if ZIP contains Playwright JSON report."""
        json_files = [n for n in namelist if n.endswith(JSON_EXT)]

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
        elif self._is_blob_report(namelist):
            return self._extract_blob_report(zip_file, output_dir)
        else:
            return self._extract_json_report(zip_file, output_dir)

    def _merge_stats(self, combined_stats: dict, new_stats: dict) -> None:
        """Merge new stats into combined stats."""
        for k, v in new_stats.items():
            if isinstance(v, int | float):
                combined_stats[k] = combined_stats.get(k, 0) + v

    def _process_inner_zip(self, inner_zip: ZipFile, combined_data: dict) -> bool:
        """Process contents of an inner zip file, returning True if data found."""
        has_data = False
        for inner_name in inner_zip.namelist():
            if inner_name.endswith(".jsonl"):
                content = inner_zip.read(inner_name).decode("utf-8")
                self._parse_jsonl_events(content, combined_data)
                has_data = True
            elif inner_name.endswith(JSON_EXT):
                content = inner_zip.read(inner_name)
                data = json.loads(content)
                if "suites" in data:
                    combined_data["suites"].extend(data["suites"])
                    has_data = True
                if "stats" in data:
                    self._merge_stats(combined_data["stats"], data["stats"])
        return has_data

    def _find_blob_root(self, namelist: list[str]) -> str:
        """Find the directory containing blob report .zip files.

        Returns the prefix (e.g., "blob-report/") or empty string for root.
        """
        # Group .zip files by parent directory
        dirs_with_zips: dict[str, int] = {}
        for name in namelist:
            if name.endswith(".zip"):
                if "/" in name:
                    parent = name.rsplit("/", 1)[0] + "/"
                else:
                    parent = ""
                dirs_with_zips[parent] = dirs_with_zips.get(parent, 0) + 1

        # Return directory with most .zip files that's not an HTML report
        for prefix in sorted(dirs_with_zips, key=lambda p: dirs_with_zips[p], reverse=True):
            index_path = f"{prefix}{INDEX_HTML}" if prefix else INDEX_HTML
            data_path = f"{prefix}data/"
            if index_path not in namelist and not any(n.startswith(data_path) for n in namelist):
                return prefix
        return ""

    def _extract_blob_report(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract blob format report.

        Blob reports contain .zip files with test data that can be merged.
        Supports both JSON format and JSONL (event stream) format.
        Handles both root-level and nested blob reports.
        """
        import zipfile as zf_module

        output_dir.mkdir(parents=True, exist_ok=True)
        combined_data: dict = {
            "suites": [],
            "stats": {"passed": 0, "failed": 0, "skipped": 0, "total": 0},
        }
        has_data = False

        # Find the blob report root directory
        blob_root = self._find_blob_root(zip_file.namelist())

        for name in zip_file.namelist():
            # Check if this .zip is in the blob root directory
            if not name.endswith(".zip"):
                continue
            # For nested: "blob-report/file.zip" with blob_root="blob-report/"
            # For root: "file.zip" with blob_root=""
            if blob_root:
                if not name.startswith(blob_root):
                    continue
                # Make sure it's directly in blob_root, not deeper
                remainder = name[len(blob_root) :]
                if "/" in remainder:
                    continue
            else:
                # Root level - no "/" allowed
                if "/" in name:
                    continue

            try:
                blob_data = zip_file.read(name)
                with zf_module.ZipFile(io.BytesIO(blob_data)) as inner_zip:
                    if self._process_inner_zip(inner_zip, combined_data):
                        has_data = True
            except (zf_module.BadZipFile, json.JSONDecodeError, UnicodeDecodeError):
                continue

        report_path = output_dir / REPORT_JSON
        report_path.write_text(json.dumps(combined_data, indent=2))

        return ExtractedReport(
            report_type=ReportType.BLOB,
            root_dir=output_dir,
            data_file=report_path,
            entry_point=report_path,
            raw_data=combined_data,
            visual_only=not has_data,
        )

    def _update_stats_for_status(self, stats: dict, status: str) -> None:
        """Update stats counters based on test status."""
        stats["total"] += 1
        if status == "passed":
            stats["passed"] += 1
        elif status in ("failed", "timedOut", "interrupted"):
            stats["failed"] += 1
        elif status == "skipped":
            stats["skipped"] += 1

    def _build_specs_from_tests(self, tests_by_id: dict) -> list[dict]:
        """Build Playwright spec format from tests dictionary."""
        specs = []
        for test_data in tests_by_id.values():
            specs.append(
                {
                    "title": test_data["title"],
                    "tests": [
                        {
                            "status": "expected"
                            if test_data["status"] == "passed"
                            else "unexpected",
                            "results": [
                                {
                                    "status": test_data["status"],
                                    "duration": test_data["duration"],
                                    "errors": test_data["errors"],
                                }
                            ],
                        }
                    ],
                }
            )
        return specs

    def _parse_jsonl_events(self, content: str, combined_data: dict) -> None:
        """Parse JSONL event stream from Playwright blob reporter.

        Extracts test results from onTestEnd events and aggregates stats.
        """
        tests_by_id: dict = {}

        for line in content.strip().split("\n"):
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("method") != "onTestEnd":
                    continue

                params = event.get("params", {})
                test_info = params.get("test", {})
                result_info = params.get("result", {})

                status = result_info.get("status", "passed")
                tests_by_id[test_info.get("testId", "")] = {
                    "title": test_info.get("title", "Unknown"),
                    "status": status,
                    "duration": result_info.get("duration", 0),
                    "errors": result_info.get("errors", []),
                }
                self._update_stats_for_status(combined_data["stats"], status)

            except json.JSONDecodeError:
                continue

        if tests_by_id:
            combined_data["suites"].append(
                {"title": "Blob Report Tests", "specs": self._build_specs_from_tests(tests_by_id)}
            )

    def _extract_json_report(self, zip_file: ZipFile, output_dir: Path) -> ExtractedReport:
        """Extract JSON format report."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find and extract the JSON report file
        json_file = self._find_json_report_file(zip_file)
        if not json_file:
            raise ValueError("Could not find Playwright JSON report in ZIP")

        content = zip_file.read(json_file)
        data = json.loads(content)

        report_path = output_dir / REPORT_JSON
        report_path.write_text(json.dumps(data, indent=2))

        return ExtractedReport(
            report_type=ReportType.JSON,
            root_dir=output_dir,
            data_file=report_path,
            entry_point=report_path,
            raw_data=data,
            visual_only=False,
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
        entry_point = html_dir / INDEX_HTML
        if not entry_point.exists():
            # Try to find it in subdirectories
            for html_file in html_dir.rglob(INDEX_HTML):
                entry_point = html_file
                break

        # For HTML reports, we need to extract JSON data from data/ directory
        # The data files contain the actual test results
        data_file, has_data = self._extract_data_from_html_report(html_dir, output_dir)

        # Mark as visual_only if no test data could be extracted
        visual_only = not has_data

        return ExtractedReport(
            report_type=ReportType.HTML,
            root_dir=html_dir,
            data_file=data_file,
            entry_point=entry_point,
            raw_data=None,  # Will be loaded during normalize
            visual_only=visual_only,
        )

    def _process_html_data_zip(self, inner_zip: ZipFile, combined_data: dict) -> bool:
        """Process a single data zip from HTML report, returning True if suites found."""
        has_data = False
        for name in inner_zip.namelist():
            if not name.endswith(JSON_EXT):
                continue
            content = inner_zip.read(name)
            data = json.loads(content)
            if "suites" in data:
                combined_data["suites"].extend(data["suites"])
                if data["suites"]:
                    has_data = True
            if "stats" in data:
                self._merge_stats(combined_data["stats"], data["stats"])
        return has_data

    def _extract_data_from_html_report(self, html_dir: Path, output_dir: Path) -> tuple[Path, bool]:
        """Extract JSON data from HTML report's data directory.

        Playwright HTML reports store test data in data/*.zip files.
        We need to extract and combine them.

        Returns:
            Tuple of (report_path, has_data) where has_data indicates
            whether any test data was successfully extracted.
        """
        import zipfile as zf_module

        data_dir = html_dir / "data"
        combined_data: dict = {"suites": [], "stats": {}}
        has_data = False

        if data_dir.exists():
            for data_file in data_dir.glob("*.zip"):
                try:
                    with zf_module.ZipFile(data_file) as inner_zip:
                        if self._process_html_data_zip(inner_zip, combined_data):
                            has_data = True
                except (zf_module.BadZipFile, json.JSONDecodeError):
                    continue

        report_path = output_dir / REPORT_JSON
        report_path.write_text(json.dumps(combined_data, indent=2))

        return report_path, has_data

    def _find_json_report_file(self, zip_file: ZipFile) -> str | None:
        """Find the main JSON report file in the ZIP."""
        namelist = zip_file.namelist()

        # Priority order for finding the report
        candidates = [
            REPORT_JSON,
            "playwright-report.json",
            "results.json",
        ]

        for candidate in candidates:
            if candidate in namelist:
                return candidate

        # Fall back to any JSON file that looks like a Playwright report
        for name in namelist:
            if name.endswith(JSON_EXT):
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

        # Calculate totals - support both JSON reporter format (expected/unexpected)
        # and JSONL/blob format (passed/failed)
        passed = stats.get("passed", 0) or stats.get("expected", 0)
        failed = stats.get("failed", 0) or (stats.get("unexpected", 0) + stats.get("flaky", 0))
        skipped = stats.get("skipped", 0)
        total = stats.get("total", 0) or (passed + failed + skipped)

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
