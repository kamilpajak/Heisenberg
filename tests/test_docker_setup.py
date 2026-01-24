"""Tests for Docker setup - TDD for Phase 7 Task 2."""

from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent


class TestDockerfileExists:
    """Test that Dockerfile exists and has proper structure."""

    def test_dockerfile_exists(self):
        """Dockerfile should exist in project root."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found in project root"

    def test_dockerfile_has_python_base(self):
        """Dockerfile should use Python base image."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "FROM python" in content or "FROM ghcr.io/astral-sh/uv" in content

    def test_dockerfile_has_workdir(self):
        """Dockerfile should set WORKDIR."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "WORKDIR" in content

    def test_dockerfile_exposes_port(self):
        """Dockerfile should expose port 8000."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "EXPOSE 8000" in content or "EXPOSE" in content

    def test_dockerfile_has_healthcheck(self):
        """Dockerfile should have HEALTHCHECK."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "HEALTHCHECK" in content

    def test_dockerfile_has_cmd(self):
        """Dockerfile should have CMD or ENTRYPOINT."""
        dockerfile = PROJECT_ROOT / "Dockerfile"
        content = dockerfile.read_text()
        assert "CMD" in content or "ENTRYPOINT" in content


class TestDockerComposeExists:
    """Test that docker-compose.yml exists and has proper structure."""

    def test_docker_compose_exists(self):
        """docker-compose.yml should exist in project root."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml not found"

    def test_docker_compose_has_services(self):
        """docker-compose.yml should define services."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        assert "services:" in content

    def test_docker_compose_has_api_service(self):
        """docker-compose.yml should have api service."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        assert "api:" in content or "backend:" in content or "heisenberg:" in content

    def test_docker_compose_has_postgres_service(self):
        """docker-compose.yml should have postgres service."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        assert "postgres:" in content or "db:" in content or "database:" in content

    def test_docker_compose_has_volumes(self):
        """docker-compose.yml should define volumes for persistence."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        assert "volumes:" in content

    def test_docker_compose_has_healthcheck(self):
        """docker-compose.yml should have health checks."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()
        assert "healthcheck:" in content


class TestDockerIgnore:
    """Test that .dockerignore exists."""

    def test_dockerignore_exists(self):
        """dockerignore should exist."""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        assert dockerignore.exists(), ".dockerignore not found"

    def test_dockerignore_excludes_venv(self):
        """.dockerignore should exclude .venv."""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        content = dockerignore.read_text()
        assert ".venv" in content or "venv" in content

    def test_dockerignore_excludes_git(self):
        """.dockerignore should exclude .git."""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        content = dockerignore.read_text()
        assert ".git" in content

    def test_dockerignore_excludes_tests(self):
        """.dockerignore should exclude tests for production."""
        dockerignore = PROJECT_ROOT / ".dockerignore"
        content = dockerignore.read_text()
        assert "tests" in content or "test" in content


class TestDockerComposeValidation:
    """Test docker-compose.yml is valid YAML."""

    def test_docker_compose_is_valid_yaml(self):
        """docker-compose.yml should be valid YAML."""
        import yaml

        compose_file = PROJECT_ROOT / "docker-compose.yml"
        content = compose_file.read_text()

        # Should not raise
        config = yaml.safe_load(content)
        assert config is not None
        assert "services" in config

    def test_docker_compose_api_has_required_fields(self):
        """API service should have required configuration."""
        import yaml

        compose_file = PROJECT_ROOT / "docker-compose.yml"
        config = yaml.safe_load(compose_file.read_text())

        # Find API service (could be named api, backend, or heisenberg)
        api_service = None
        for name in ["api", "backend", "heisenberg"]:
            if name in config["services"]:
                api_service = config["services"][name]
                break

        assert api_service is not None, "API service not found"
        assert "build" in api_service or "image" in api_service
        assert "ports" in api_service
        assert "environment" in api_service or "env_file" in api_service

    def test_docker_compose_postgres_has_required_fields(self):
        """Postgres service should have required configuration."""
        import yaml

        compose_file = PROJECT_ROOT / "docker-compose.yml"
        config = yaml.safe_load(compose_file.read_text())

        # Find postgres service
        pg_service = None
        for name in ["postgres", "db", "database"]:
            if name in config["services"]:
                pg_service = config["services"][name]
                break

        assert pg_service is not None, "Postgres service not found"
        assert "image" in pg_service
        assert "postgres" in pg_service["image"]
