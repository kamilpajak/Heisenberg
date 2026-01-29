"""Tests for MkDocs documentation site."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestDocsStructure:
    """Validate MkDocs documentation structure."""

    def test_docs_directory_exists(self):
        """Docs directory should exist for MkDocs."""
        docs_dir = PROJECT_ROOT / "docs"
        assert docs_dir.exists(), "docs/ directory must exist"

    def test_mkdocs_config_exists(self):
        """MkDocs configuration file should exist."""
        mkdocs_yml = PROJECT_ROOT / "mkdocs.yml"
        assert mkdocs_yml.exists(), "mkdocs.yml must exist"

    def test_index_md_exists(self):
        """Landing page index.md should exist."""
        index_path = PROJECT_ROOT / "docs" / "index.md"
        assert index_path.exists(), "docs/index.md must exist"

    def test_landing_page_has_title(self):
        """Landing page should have a title."""
        index_path = PROJECT_ROOT / "docs" / "index.md"
        content = index_path.read_text()
        assert "# Heisenberg" in content

    def test_landing_page_has_description(self):
        """Landing page should describe the product."""
        index_path = PROJECT_ROOT / "docs" / "index.md"
        content = index_path.read_text().lower()
        assert "flaky" in content or "test" in content

    def test_landing_page_has_features(self):
        """Landing page should list features."""
        index_path = PROJECT_ROOT / "docs" / "index.md"
        content = index_path.read_text().lower()
        assert "feature" in content or "playwright" in content


class TestDocsContent:
    """Validate documentation content."""

    def test_getting_started_exists(self):
        """Getting started guide should exist."""
        path = PROJECT_ROOT / "docs" / "getting-started" / "installation.md"
        assert path.exists(), "Installation guide must exist"

    def test_quickstart_exists(self):
        """Quick start guide should exist."""
        path = PROJECT_ROOT / "docs" / "getting-started" / "quickstart.md"
        assert path.exists(), "Quickstart guide must exist"

    def test_cli_reference_exists(self):
        """CLI reference should exist."""
        path = PROJECT_ROOT / "docs" / "guide" / "cli.md"
        assert path.exists(), "CLI reference must exist"
