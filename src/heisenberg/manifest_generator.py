"""Generate manifest.json from frozen scenarios.

This module aggregates all frozen scenarios into a manifest file
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

    scenarios_dir: Path
    output_path: Path | None = None
    include_pending: bool = False

    def __post_init__(self):
        """Set default output path if not provided."""
        if self.output_path is None:
            self.output_path = self.scenarios_dir / "manifest.json"


@dataclass
class ScenarioEntry:
    """Entry for a single scenario in the manifest."""

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
    """Generated manifest with all scenarios and stats."""

    scenarios: list[ScenarioEntry]
    stats: dict[str, int]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "generated_at": self.generated_at,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "stats": self.stats,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


class ManifestGenerator:
    """Generates manifest.json from frozen scenarios."""

    def __init__(self, config: GeneratorConfig):
        """Initialize generator with configuration.

        Args:
            config: GeneratorConfig with scenarios_dir and optional settings.
        """
        self.config = config

    def discover_scenarios(self) -> list[Path]:
        """Discover all scenario directories.

        Returns:
            List of paths to scenario directories.
        """
        if not self.config.scenarios_dir.exists():
            return []

        return [p for p in sorted(self.config.scenarios_dir.iterdir()) if p.is_dir()]

    def load_scenario(self, scenario_dir: Path) -> ScenarioEntry:
        """Load scenario data from directory.

        Args:
            scenario_dir: Path to scenario directory.

        Returns:
            ScenarioEntry with scenario data.
        """
        scenario_id = scenario_dir.name

        # Load metadata
        metadata_path = scenario_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text())

        # Build source info
        source = {
            "repo": metadata.get("repo"),
            "repo_url": metadata.get("repo_url"),
            "stars": metadata.get("stars", 0),
            "captured_at": metadata.get("captured_at"),
            "original_run_id": metadata.get("run_id"),
        }

        # Build asset paths (relative to scenarios dir)
        assets: dict[str, str | None] = {
            "report": f"{scenario_id}/report.json"
            if (scenario_dir / "report.json").exists()
            else None,
        }

        # Check for trace
        if (scenario_dir / "trace.zip").exists():
            assets["trace"] = f"{scenario_id}/trace.zip"

        # Load diagnosis if exists
        diagnosis_path = scenario_dir / "diagnosis.json"
        if diagnosis_path.exists():
            diagnosis = json.loads(diagnosis_path.read_text())
            assets["diagnosis"] = f"{scenario_id}/diagnosis.json"

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

        return ScenarioEntry(
            id=scenario_id,
            source=source,
            assets=assets,
            validation=validation,
        )

    def generate(self) -> Manifest:
        """Generate manifest from all scenarios.

        Returns:
            Manifest with all scenarios and stats.
        """
        scenario_dirs = self.discover_scenarios()
        entries = []

        for scenario_dir in scenario_dirs:
            try:
                entry = self.load_scenario(scenario_dir)

                # Skip pending unless include_pending is set
                if entry.validation.get("status") == "pending" and not self.config.include_pending:
                    continue

                entries.append(entry)
            except (json.JSONDecodeError, FileNotFoundError):
                # Skip invalid scenarios
                continue

        stats = self._calculate_stats(entries)
        generated_at = datetime.now(UTC).isoformat()

        return Manifest(
            scenarios=entries,
            stats=stats,
            generated_at=generated_at,
        )

    def _calculate_stats(self, entries: list[ScenarioEntry]) -> dict[str, int]:
        """Calculate statistics from scenario entries.

        Args:
            entries: List of scenario entries.

        Returns:
            Dictionary with stats.
        """
        stats = {
            "total_scenarios": len(entries),
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
