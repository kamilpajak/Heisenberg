"""Tests for release readiness - TDD for Phase 8 Release."""

import re
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestVersionConsistency:
    """Test that version is consistent across all files."""

    def test_pyproject_has_version(self):
        """pyproject.toml should have version."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert 'version = "' in content

    def test_app_has_version(self):
        """app.py should have __version__."""
        app_file = PROJECT_ROOT / "src" / "heisenberg" / "backend" / "app.py"
        content = app_file.read_text()
        assert "__version__" in content

    def test_versions_match(self):
        """Version in pyproject.toml should match app.py."""
        # Get version from pyproject.toml
        pyproject = PROJECT_ROOT / "pyproject.toml"
        pyproject_content = pyproject.read_text()
        pyproject_match = re.search(r'version = "([^"]+)"', pyproject_content)
        assert pyproject_match, "Version not found in pyproject.toml"
        pyproject_version = pyproject_match.group(1)

        # Get version from app.py
        app_file = PROJECT_ROOT / "src" / "heisenberg" / "backend" / "app.py"
        app_content = app_file.read_text()
        app_match = re.search(r'__version__ = "([^"]+)"', app_content)
        assert app_match, "__version__ not found in app.py"
        app_version = app_match.group(1)

        assert pyproject_version == app_version, (
            f"Version mismatch: pyproject.toml={pyproject_version}, app.py={app_version}"
        )


class TestChangelog:
    """Test CHANGELOG file."""

    def test_changelog_exists(self):
        """CHANGELOG.md should exist."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        assert changelog.exists(), "CHANGELOG.md not found"

    def test_changelog_has_content(self):
        """CHANGELOG.md should have content."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        assert len(content) > 100, "CHANGELOG.md seems too short"

    def test_changelog_has_version_header(self):
        """CHANGELOG.md should have version headers."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        # Should have at least one version header like ## [0.1.0] or ## 0.1.0
        assert re.search(r"##\s*\[?\d+\.\d+\.\d+\]?", content), (
            "No version header found in CHANGELOG.md"
        )

    def test_changelog_has_unreleased_or_latest(self):
        """CHANGELOG.md should document latest changes."""
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        content = changelog.read_text()
        # Should have Unreleased section or a recent version
        has_unreleased = "Unreleased" in content or "unreleased" in content
        has_version = re.search(r"##\s*\[?\d+\.\d+\.\d+\]?", content)
        assert has_unreleased or has_version


class TestPackageMetadata:
    """Test package metadata in pyproject.toml."""

    def test_has_name(self):
        """pyproject.toml should have name."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert 'name = "heisenberg"' in content

    def test_has_description(self):
        """pyproject.toml should have description."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "description = " in content

    def test_has_authors(self):
        """pyproject.toml should have authors."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "authors = " in content

    def test_has_license(self):
        """pyproject.toml should have license."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "license = " in content

    def test_has_python_requires(self):
        """pyproject.toml should specify Python version."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "requires-python" in content

    def test_has_classifiers(self):
        """pyproject.toml should have classifiers."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "classifiers = " in content

    def test_has_keywords(self):
        """pyproject.toml should have keywords."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "keywords = " in content


class TestLicenseFile:
    """Test LICENSE file."""

    def test_license_file_exists(self):
        """LICENSE file should exist."""
        license_file = PROJECT_ROOT / "LICENSE"
        assert license_file.exists(), "LICENSE file not found"

    def test_license_has_content(self):
        """LICENSE file should have content."""
        license_file = PROJECT_ROOT / "LICENSE"
        content = license_file.read_text()
        assert len(content) > 100, "LICENSE file seems too short"

    def test_license_is_mit(self):
        """LICENSE should be MIT (as specified in pyproject.toml)."""
        license_file = PROJECT_ROOT / "LICENSE"
        content = license_file.read_text()
        assert "MIT" in content or "Permission is hereby granted" in content


class TestReadme:
    """Test README file."""

    def test_readme_exists(self):
        """README.md should exist."""
        readme = PROJECT_ROOT / "README.md"
        assert readme.exists(), "README.md not found"

    def test_readme_has_project_name(self):
        """README.md should mention project name."""
        readme = PROJECT_ROOT / "README.md"
        content = readme.read_text()
        assert "Heisenberg" in content or "heisenberg" in content

    def test_readme_has_installation(self):
        """README.md should have installation instructions."""
        readme = PROJECT_ROOT / "README.md"
        content = readme.read_text().lower()
        assert "install" in content or "pip" in content or "uv" in content

    def test_readme_has_usage(self):
        """README.md should have usage section."""
        readme = PROJECT_ROOT / "README.md"
        content = readme.read_text().lower()
        assert "usage" in content or "example" in content or "getting started" in content


class TestBuildability:
    """Test that package can be built."""

    def test_pyproject_is_valid_toml(self):
        """pyproject.toml should be valid TOML."""
        import tomllib

        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        # Should not raise
        data = tomllib.loads(content)
        assert "project" in data

    def test_has_build_system(self):
        """pyproject.toml should have build-system."""
        import tomllib

        pyproject = PROJECT_ROOT / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text())
        assert "build-system" in data
        assert "requires" in data["build-system"]
        assert "build-backend" in data["build-system"]

    def test_package_structure_valid(self):
        """Package structure should be valid."""
        src_dir = PROJECT_ROOT / "src" / "heisenberg"
        assert src_dir.exists(), "src/heisenberg not found"
        assert (src_dir / "__init__.py").exists(), "src/heisenberg/__init__.py not found"
