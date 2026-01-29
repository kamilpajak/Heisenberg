"""Tests for OpenAPI documentation quality - TDD for Phase 7 Task 4."""

from fastapi.testclient import TestClient


class TestOpenAPIMetadata:
    """Test OpenAPI spec metadata."""

    def test_openapi_has_title(self):
        """OpenAPI spec should have title."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        assert "info" in data
        assert "title" in data["info"]
        assert len(data["info"]["title"]) > 0

    def test_openapi_has_description(self):
        """OpenAPI spec should have description."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        assert "description" in data["info"]
        assert len(data["info"]["description"]) > 0

    def test_openapi_has_version(self):
        """OpenAPI spec should have version."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        assert "version" in data["info"]
        assert data["info"]["version"]


class TestEndpointDocumentation:
    """Test that endpoints have proper documentation."""

    def test_analyze_endpoint_has_summary(self):
        """Analyze endpoint should have summary."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        analyze_path = data["paths"].get("/api/v1/analyze/", {})
        post_op = analyze_path.get("post", {})

        assert "summary" in post_op
        assert len(post_op["summary"]) > 0

    def test_analyze_endpoint_has_description(self):
        """Analyze endpoint should have description."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        analyze_path = data["paths"].get("/api/v1/analyze/", {})
        post_op = analyze_path.get("post", {})

        assert "description" in post_op
        assert len(post_op["description"]) > 0

    def test_health_endpoint_has_tags(self):
        """Health endpoint should have tags."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        health_path = data["paths"].get("/health", {})
        get_op = health_path.get("get", {})

        assert "tags" in get_op
        assert len(get_op["tags"]) > 0

    def test_feedback_endpoint_has_documentation(self):
        """Feedback endpoint should have documentation."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        # Find feedback endpoint
        feedback_found = False
        for path, methods in data["paths"].items():
            if "feedback" in path:
                feedback_found = True
                for method, op in methods.items():
                    if method in ["get", "post", "put", "delete"]:
                        assert "summary" in op or "description" in op
                break

        assert feedback_found, "Feedback endpoint not found in OpenAPI spec"


class TestSchemaDocumentation:
    """Test that schemas have proper documentation."""

    def test_schemas_section_exists(self):
        """OpenAPI spec should have schemas section."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        assert "components" in data
        assert "schemas" in data["components"]

    def test_analyze_request_schema_documented(self):
        """AnalyzeRequest schema should be documented."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        schemas = data["components"]["schemas"]
        assert "AnalyzeRequest" in schemas

        schema = schemas["AnalyzeRequest"]
        assert "properties" in schema

    def test_analyze_response_schema_documented(self):
        """AnalyzeResponse schema should be documented."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        schemas = data["components"]["schemas"]
        assert "AnalyzeResponse" in schemas

    def test_schema_properties_have_descriptions(self):
        """Schema properties should have descriptions."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        schemas = data["components"]["schemas"]
        analyze_request = schemas.get("AnalyzeRequest", {})
        properties = analyze_request.get("properties", {})

        # At least repository should have description
        if "repository" in properties:
            assert "description" in properties["repository"]


class TestResponseDocumentation:
    """Test that responses are documented."""

    def test_analyze_endpoint_documents_responses(self):
        """Analyze endpoint should document response codes."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        analyze_path = data["paths"].get("/api/v1/analyze/", {})
        post_op = analyze_path.get("post", {})

        assert "responses" in post_op
        # Should document at least success response
        responses = post_op["responses"]
        assert any(code.startswith("2") for code in responses.keys())

    def test_health_endpoint_documents_200_response(self):
        """Health endpoint should document 200 response."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        health_path = data["paths"].get("/health", {})
        get_op = health_path.get("get", {})

        assert "responses" in get_op
        assert "200" in get_op["responses"]


class TestTagsOrganization:
    """Test that endpoints are organized with tags."""

    def test_tags_are_defined(self):
        """OpenAPI spec should define tags."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        # Tags may be defined at top level or inferred from endpoints
        has_tags = "tags" in data or any(
            "tags" in op
            for path_ops in data["paths"].values()
            for op in path_ops.values()
            if isinstance(op, dict)
        )
        assert has_tags

    def test_analysis_endpoints_tagged(self):
        """Analysis endpoints should be tagged."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        analyze_path = data["paths"].get("/api/v1/analyze/", {})
        post_op = analyze_path.get("post", {})

        assert "tags" in post_op
        assert "Analysis" in post_op["tags"]

    def test_health_endpoints_tagged(self):
        """Health endpoints should be tagged."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        health_path = data["paths"].get("/health", {})
        get_op = health_path.get("get", {})

        assert "tags" in get_op
        assert "Health" in get_op["tags"]


class TestSecurityDocumentation:
    """Test security scheme documentation."""

    def test_security_schemes_defined(self):
        """OpenAPI spec should define security schemes."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        # Security schemes should be defined in components
        components = data.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        # Should have API key security scheme
        assert len(security_schemes) > 0 or "security" in data

    def test_analyze_endpoint_requires_auth(self):
        """Analyze endpoint should document auth requirement."""
        from heisenberg.backend.app import app

        client = TestClient(app)
        response = client.get("/openapi.json")
        data = response.json()

        analyze_path = data["paths"].get("/api/v1/analyze/", {})
        post_op = analyze_path.get("post", {})

        # Should have security requirement or parameters for API key
        has_security = "security" in post_op
        has_api_key_param = any(
            p.get("name") == "X-API-Key" or p.get("name") == "api_key"
            for p in post_op.get("parameters", [])
        )

        assert has_security or has_api_key_param
