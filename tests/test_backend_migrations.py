"""Tests for backend Alembic migrations - TDD for Phase 5."""

import ast
from pathlib import Path


class TestAlembicSetup:
    """Test suite for Alembic setup."""

    def test_alembic_ini_exists(self):
        """alembic.ini should exist in project root."""
        alembic_ini = Path("alembic.ini")
        assert alembic_ini.exists(), "alembic.ini not found"

    def test_migrations_directory_exists(self):
        """migrations directory should exist."""
        migrations_dir = Path("migrations")
        assert migrations_dir.exists(), "migrations directory not found"
        assert migrations_dir.is_dir(), "migrations should be a directory"

    def test_env_py_exists(self):
        """migrations/env.py should exist."""
        env_py = Path("migrations/env.py")
        assert env_py.exists(), "migrations/env.py not found"

    def test_versions_directory_exists(self):
        """migrations/versions directory should exist."""
        versions_dir = Path("migrations/versions")
        assert versions_dir.exists(), "migrations/versions directory not found"
        assert versions_dir.is_dir(), "migrations/versions should be a directory"

    def test_script_py_mako_exists(self):
        """migrations/script.py.mako should exist."""
        script_mako = Path("migrations/script.py.mako")
        assert script_mako.exists(), "migrations/script.py.mako not found"


class TestAlembicConfiguration:
    """Test suite for Alembic configuration."""

    def test_alembic_ini_has_script_location(self):
        """alembic.ini should configure script_location."""
        alembic_ini = Path("alembic.ini")
        content = alembic_ini.read_text()
        assert "script_location = migrations" in content

    def test_env_py_imports_models(self):
        """env.py should import models for autogenerate."""
        env_py = Path("migrations/env.py")
        content = env_py.read_text()
        assert "heisenberg.backend.models" in content

    def test_env_py_sets_target_metadata(self):
        """env.py should set target_metadata from models.Base."""
        env_py = Path("migrations/env.py")
        content = env_py.read_text()
        assert "target_metadata" in content
        assert "Base.metadata" in content


class TestInitialMigration:
    """Test suite for initial migration script."""

    def test_initial_migration_exists(self):
        """Initial migration script should exist."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1, "Initial migration not found"

    def test_migration_has_upgrade_function(self):
        """Migration should have upgrade() function."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        tree = ast.parse(content)

        upgrade_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
                upgrade_found = True
                break

        assert upgrade_found, "upgrade() function not found in migration"

    def test_migration_has_downgrade_function(self):
        """Migration should have downgrade() function."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        tree = ast.parse(content)

        downgrade_found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
                downgrade_found = True
                break

        assert downgrade_found, "downgrade() function not found in migration"

    def test_migration_creates_organizations_table(self):
        """Migration should create organizations table."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        assert "organizations" in content, "organizations table not in migration"

    def test_migration_creates_api_keys_table(self):
        """Migration should create api_keys table."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        assert "api_keys" in content, "api_keys table not in migration"

    def test_migration_creates_test_runs_table(self):
        """Migration should create test_runs table."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        assert "test_runs" in content, "test_runs table not in migration"

    def test_migration_creates_analyses_table(self):
        """Migration should create analyses table."""
        versions_dir = Path("migrations/versions")
        migration_files = list(versions_dir.glob("*_initial*.py"))
        assert len(migration_files) >= 1

        content = migration_files[0].read_text()
        assert "analyses" in content, "analyses table not in migration"
