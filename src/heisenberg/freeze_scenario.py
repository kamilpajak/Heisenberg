"""Freeze GitHub Actions artifacts into local snapshots for demo.

This module downloads Playwright test artifacts from GitHub Actions
and saves them locally as "frozen scenarios" for the Heisenberg playground.
"""

from __future__ import annotations

import io
import json
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

from heisenberg.github_artifacts import GitHubArtifactClient
from heisenberg.reports import ReportType, get_default_registry


@dataclass
class FreezeConfig:
    """Configuration for freezing a scenario."""

    repo: str  # Format: "owner/repo"
    output_dir: Path
    github_token: str | None = None
    run_id: int | None = None  # If None, find latest failed run


@dataclass
class ScenarioMetadata:
    """Metadata about the frozen scenario's source."""

    repo: str
    repo_url: str
    stars: int
    run_id: int
    run_url: str
    captured_at: str
    artifact_names: list[str] = field(default_factory=list)


@dataclass
class FrozenScenario:
    """Result of freezing a scenario - paths to frozen assets."""

    id: str
    scenario_dir: Path
    metadata_path: Path
    report_path: Path
    trace_path: Path | None = None
    logs_path: Path | None = None
    report_type: ReportType = ReportType.JSON
    html_report_path: Path | None = None  # For HTML reports, path to index.html
    visual_only: bool = False  # True if report can only be viewed, not analyzed


def get_repo_stars(repo: str) -> int:
    """Get star count for a repository using gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "api", f"/repos/{repo}", "--jq", ".stargazers_count"],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0


class ScenarioFreezer:
    """Freezes GitHub Actions artifacts into local snapshots."""

    # Patterns that indicate Playwright-related artifacts
    PLAYWRIGHT_PATTERNS = [
        "playwright",
        "blob-report",
        "test-results",
        "e2e-report",
        "e2e-test",
    ]

    # Patterns for trace artifacts
    TRACE_PATTERNS = ["trace", "traces"]

    def __init__(self, config: FreezeConfig):
        """Initialize freezer with configuration.

        Args:
            config: FreezeConfig with repo, output_dir, and optional settings.
        """
        self.config = config
        self._client: GitHubArtifactClient | None = None

    @property
    def client(self) -> GitHubArtifactClient:
        """Lazy-initialize GitHub client."""
        if self._client is None:
            token = self.config.github_token or self._get_token_from_gh()
            if not token:
                raise ValueError("GitHub token required. Set github_token or login with gh CLI.")
            self._client = GitHubArtifactClient(token=token)
        return self._client

    def _get_token_from_gh(self) -> str | None:
        """Try to get token from gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _generate_scenario_id(self) -> str:
        """Generate a filesystem-safe scenario ID."""
        # Replace / with - and add run_id
        repo_slug = self.config.repo.replace("/", "-").lower()
        run_id = self.config.run_id or "latest"
        return f"{repo_slug}-{run_id}"

    def _is_playwright_artifact(self, name: str) -> bool:
        """Check if artifact name suggests Playwright report."""
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in self.PLAYWRIGHT_PATTERNS)

    def _is_trace_artifact(self, name: str) -> bool:
        """Check if artifact name suggests Playwright traces."""
        name_lower = name.lower()
        return any(pattern in name_lower for pattern in self.TRACE_PATTERNS)

    def _parse_owner_repo(self) -> tuple[str, str]:
        """Parse owner and repo from config.repo."""
        parts = self.config.repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {self.config.repo}. Expected 'owner/repo'.")
        return parts[0], parts[1]

    async def freeze(self) -> FrozenScenario:
        """Freeze artifacts from GitHub into local snapshot.

        Returns:
            FrozenScenario with paths to all frozen assets.

        Raises:
            ValueError: If no suitable artifacts found.
        """
        owner, repo = self._parse_owner_repo()

        # Get run_id - either from config or find latest failed
        run_id = self.config.run_id
        run_url = ""

        if run_id is None:
            runs = await self.client.list_workflow_runs(owner, repo)
            failed_runs = [r for r in runs if r.conclusion == "failure"]
            if not failed_runs:
                raise ValueError(f"No failed workflow runs found for {self.config.repo}")
            run_id = failed_runs[0].id
            run_url = failed_runs[0].html_url
        else:
            run_url = f"https://github.com/{self.config.repo}/actions/runs/{run_id}"

        # Update config with resolved run_id for ID generation
        self.config.run_id = run_id

        # Get artifacts for this run
        artifacts = await self.client.get_artifacts(owner, repo, run_id=run_id)

        # Filter for Playwright artifacts
        playwright_artifacts = [
            a for a in artifacts if self._is_playwright_artifact(a.name) and not a.expired
        ]

        if not playwright_artifacts:
            # Check if there were expired artifacts
            expired = [a for a in artifacts if self._is_playwright_artifact(a.name) and a.expired]
            if expired:
                raise ValueError(
                    f"All Playwright artifacts are expired for run {run_id}. "
                    "GitHub artifacts expire after 90 days."
                )
            raise ValueError(
                f"No Playwright artifacts found for run {run_id}. "
                f"Available artifacts: {[a.name for a in artifacts]}"
            )

        # Create scenario directory
        scenario_id = self._generate_scenario_id()
        scenario_dir = self.config.output_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Download and extract report using framework-agnostic handler
        report_artifact = playwright_artifacts[0]  # Take first Playwright artifact
        zip_data = await self.client.download_artifact(owner, repo, artifact_id=report_artifact.id)

        # Use the reports registry to identify and extract the report
        registry = get_default_registry()
        handler = registry.identify(zip_data)

        if handler is None:
            raise ValueError(f"Could not identify report format in {report_artifact.name}")

        with ZipFile(io.BytesIO(zip_data)) as zf:
            extracted = handler.extract(zf, scenario_dir)

        # Validate that the report has analyzable failures
        if not extracted.is_analyzable:
            # Clean up the created directory
            import shutil

            shutil.rmtree(scenario_dir, ignore_errors=True)
            if extracted.visual_only:
                raise ValueError(
                    f"Report from {self.config.repo} is visual-only and not analyzable. "
                    "HTML reports without extractable JSON data cannot be analyzed."
                )
            raise ValueError(
                f"Report from {self.config.repo} has no test failures to analyze. "
                f"Found {extracted.failure_count} failures."
            )

        report_path = extracted.data_file
        report_type = extracted.report_type
        visual_only = extracted.visual_only
        html_report_path = (
            extracted.entry_point if extracted.report_type == ReportType.HTML else None
        )

        # Check for trace artifacts
        trace_path = None
        trace_artifacts = [
            a for a in artifacts if self._is_trace_artifact(a.name) and not a.expired
        ]
        if trace_artifacts:
            trace_data = await self.client.download_artifact(
                owner, repo, artifact_id=trace_artifacts[0].id
            )
            trace_path = scenario_dir / "trace.zip"
            trace_path.write_bytes(trace_data)

        # Get repo stars
        stars = get_repo_stars(self.config.repo)

        # Create and save metadata
        metadata = ScenarioMetadata(
            repo=self.config.repo,
            repo_url=f"https://github.com/{self.config.repo}",
            stars=stars,
            run_id=run_id,
            run_url=run_url,
            captured_at=datetime.now(UTC).isoformat(),
            artifact_names=[a.name for a in playwright_artifacts],
        )

        metadata_path = scenario_dir / "metadata.json"
        metadata_dict = {
            "repo": metadata.repo,
            "repo_url": metadata.repo_url,
            "stars": metadata.stars,
            "run_id": metadata.run_id,
            "run_url": metadata.run_url,
            "captured_at": metadata.captured_at,
            "artifact_names": metadata.artifact_names,
            "report_type": report_type.value,
            "visual_only": visual_only,
        }
        metadata_path.write_text(json.dumps(metadata_dict, indent=2))

        return FrozenScenario(
            id=scenario_id,
            scenario_dir=scenario_dir,
            metadata_path=metadata_path,
            report_path=report_path,
            trace_path=trace_path,
            report_type=report_type,
            html_report_path=html_report_path,
            visual_only=visual_only,
        )
