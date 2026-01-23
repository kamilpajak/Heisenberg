"""Tests for GitHub Pages landing page - TDD for Phase 3."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestLandingPage:
    """Validate landing page exists and has required content."""

    def test_docs_directory_exists(self):
        """Docs directory should exist for GitHub Pages."""
        docs_dir = PROJECT_ROOT / "docs"
        assert docs_dir.exists(), "docs/ directory must exist for GitHub Pages"

    def test_index_html_exists(self):
        """Landing page index.html should exist."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        assert index_path.exists(), "docs/index.html must exist"

    def test_landing_page_has_title(self):
        """Landing page should have a title."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        content = index_path.read_text()
        assert "<title>" in content
        assert "Heisenberg" in content

    def test_landing_page_has_description(self):
        """Landing page should describe the product."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        content = index_path.read_text().lower()
        assert "flaky" in content or "test" in content

    def test_landing_page_has_github_link(self):
        """Landing page should link to GitHub repo."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        content = index_path.read_text()
        assert "github.com" in content.lower()

    def test_landing_page_has_quick_start(self):
        """Landing page should have quick start or getting started section."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        content = index_path.read_text().lower()
        assert "start" in content or "install" in content

    def test_landing_page_has_features(self):
        """Landing page should list features."""
        index_path = PROJECT_ROOT / "docs" / "index.html"
        content = index_path.read_text().lower()
        assert "feature" in content or "ai" in content
