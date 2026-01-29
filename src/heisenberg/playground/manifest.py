"""Generate manifest.json from frozen cases.

This module aggregates all frozen cases into a manifest file
for the demo playground frontend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class GeneratorConfig:
    """Configuration for manifest generation."""

    cases_dir: Path
    output_path: Path | None = None
    include_pending: bool = False

    def __post_init__(self):
        """Set default output path if not provided."""
        if self.output_path is None:
            self.output_path = self.cases_dir / "manifest.json"


@dataclass
class CaseEntry:
    """Entry for a single case in the manifest."""

    id: str
    source: dict[str, Any]
    assets: dict[str, str | None]
    validation: dict[str, Any]
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "display_name": self.display_name or self._generate_display_name(),
            "source": self.source,
            "assets": {k: v for k, v in self.assets.items() if v is not None},
            "validation": self.validation,
        }

    def _generate_display_name(self) -> str:
        """Generate display name from repo and confidence."""
        repo = self.source.get("repo", "Unknown")
        confidence = self.validation.get("confidence", "UNKNOWN")
        return f"{repo} ({confidence})"


@dataclass
class Manifest:
    """Generated manifest with all cases and stats."""

    cases: list[CaseEntry]
    stats: dict[str, int]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "generated_at": self.generated_at,
            "cases": [s.to_dict() for s in self.cases],
            "stats": self.stats,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ManifestGenerator:
    """Generates manifest.json from frozen cases."""

    def __init__(self, config: GeneratorConfig):
        """Initialize generator with configuration.

        Args:
            config: GeneratorConfig with cases_dir and optional settings.
        """
        self.config = config

    def discover_cases(self) -> list[Path]:
        """Discover all case directories.

        Returns:
            List of paths to case directories.
        """
        if not self.config.cases_dir.exists():
            return []

        return [p for p in sorted(self.config.cases_dir.iterdir()) if p.is_dir()]

    def load_case(self, case_dir: Path) -> CaseEntry:
        """Load case data from directory.

        Args:
            case_dir: Path to case directory.

        Returns:
            CaseEntry with case data.
        """
        case_id = case_dir.name

        # Load metadata
        metadata_path = case_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        # Build source info
        source = {
            "repo": metadata.get("repo"),
            "repo_url": metadata.get("repo_url"),
            "stars": metadata.get("stars", 0),
            "captured_at": metadata.get("captured_at"),
            "original_run_id": metadata.get("run_id"),
        }

        # Build asset paths (relative to cases dir)
        assets: dict[str, str | None] = {
            "report": f"{case_id}/report.json" if (case_dir / "report.json").exists() else None,
        }

        # Check for trace
        if (case_dir / "trace.zip").exists():
            assets["trace"] = f"{case_id}/trace.zip"

        # Load diagnosis if exists
        diagnosis_path = case_dir / "diagnosis.json"
        if diagnosis_path.exists():
            diagnosis = json.loads(diagnosis_path.read_text())
            assets["diagnosis"] = f"{case_id}/diagnosis.json"

            validation = {
                "status": "analyzed",
                "confidence": diagnosis.get("diagnosis", {}).get("confidence", "UNKNOWN"),
                "root_cause": diagnosis.get("diagnosis", {}).get("root_cause", ""),
                "analyzed_at": diagnosis.get("analyzed_at"),
            }
        else:
            validation = {
                "status": "pending",
                "confidence": None,
            }

        return CaseEntry(
            id=case_id,
            source=source,
            assets=assets,
            validation=validation,
        )

    def generate(self) -> Manifest:
        """Generate manifest from all cases.

        Returns:
            Manifest with all cases and stats.
        """
        case_dirs = self.discover_cases()
        entries = []

        for case_dir in case_dirs:
            try:
                entry = self.load_case(case_dir)

                # Skip pending unless include_pending is set
                if entry.validation.get("status") == "pending" and not self.config.include_pending:
                    continue

                entries.append(entry)
            except (json.JSONDecodeError, FileNotFoundError):
                # Skip invalid cases
                continue

        stats = self._calculate_stats(entries)
        generated_at = datetime.now(UTC).isoformat()

        return Manifest(
            cases=entries,
            stats=stats,
            generated_at=generated_at,
        )

    def _calculate_stats(self, entries: list[CaseEntry]) -> dict[str, int]:
        """Calculate statistics from case entries.

        Args:
            entries: List of case entries.

        Returns:
            Dictionary with stats.
        """
        stats = {
            "total_cases": len(entries),
            "high_confidence": 0,
            "medium_confidence": 0,
            "low_confidence": 0,
            "pending": 0,
        }

        for entry in entries:
            confidence = entry.validation.get("confidence")
            if confidence == "HIGH":
                stats["high_confidence"] += 1
            elif confidence == "MEDIUM":
                stats["medium_confidence"] += 1
            elif confidence == "LOW":
                stats["low_confidence"] += 1
            elif entry.validation.get("status") == "pending":
                stats["pending"] += 1

        return stats

    def save(self, manifest: Manifest) -> Path:
        """Save manifest to file.

        Args:
            manifest: Manifest to save.

        Returns:
            Path to saved manifest file.
        """
        output_path = self.config.output_path
        assert output_path is not None  # Set in __post_init__
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(manifest.to_json())
        return output_path

    def generate_and_save(self) -> Manifest:
        """Generate manifest and save to file.

        Returns:
            Generated manifest.
        """
        manifest = self.generate()
        self.save(manifest)
        return manifest
