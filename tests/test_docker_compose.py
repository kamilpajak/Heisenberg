"""Tests for Docker Compose configuration - TDD for Phase 4."""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent


class TestDockerCompose:
    """Test suite for Docker Compose configuration."""

    def test_docker_compose_exists(self):
        """docker-compose.yml should exist."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml must exist"

    def test_docker_compose_is_valid_yaml(self):
        """docker-compose.yml should be valid YAML."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        content = compose_path.read_text()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)

    def test_docker_compose_has_services(self):
        """docker-compose.yml should define services."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_path.read_text())
        assert "services" in parsed

    def test_docker_compose_has_api_service(self):
        """docker-compose.yml should have api service."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_path.read_text())
        assert "api" in parsed["services"]

    def test_docker_compose_has_postgres_service(self):
        """docker-compose.yml should have postgres service."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_path.read_text())
        assert "postgres" in parsed["services"] or "db" in parsed["services"]

    def test_docker_compose_api_depends_on_postgres(self):
        """API service should depend on postgres."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_path.read_text())
        api_service = parsed["services"]["api"]
        depends = api_service.get("depends_on", [])
        # depends_on can be list or dict
        if isinstance(depends, dict):
            depends = list(depends.keys())
        assert "postgres" in depends or "db" in depends

    def test_docker_compose_has_volumes(self):
        """docker-compose.yml should define volumes for persistence."""
        compose_path = PROJECT_ROOT / "docker-compose.yml"
        parsed = yaml.safe_load(compose_path.read_text())
        assert "volumes" in parsed


class TestDockerfile:
    """Test suite for Dockerfile."""

    def test_dockerfile_exists(self):
        """Dockerfile should exist."""
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile must exist"

    def test_dockerfile_has_python_base(self):
        """Dockerfile should use Python base image."""
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        content = dockerfile_path.read_text()
        assert "python" in content.lower()

    def test_dockerfile_exposes_port(self):
        """Dockerfile should expose a port."""
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        content = dockerfile_path.read_text()
        assert "EXPOSE" in content

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile should have a healthcheck."""
        dockerfile_path = PROJECT_ROOT / "Dockerfile"
        content = dockerfile_path.read_text()
        assert "HEALTHCHECK" in content or "health" in content.lower()
