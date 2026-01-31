"""Tests for discovery CLI - argument parsing and main entry point."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from heisenberg.discovery.cli import create_argument_parser, main
from heisenberg.discovery.models import ProjectSource, SourceStatus

# =============================================================================
# ARGUMENT PARSER TESTS
# =============================================================================


class TestArgumentParser:
    """Tests for CLI argument parser."""

    def test_parser_accepts_repo_argument(self):
        """Parser should accept --repo argument."""
        parser = create_argument_parser()
        args = parser.parse_args(["--repo", "owner/repo"])

        assert args.repo == "owner/repo"

    def test_repo_argument_is_optional(self):
        """--repo should be optional (default: None)."""
        parser = create_argument_parser()
        args = parser.parse_args([])

        assert args.repo is None

    def test_repo_with_other_arguments(self):
        """--repo should work with other arguments."""
        parser = create_argument_parser()
        args = parser.parse_args(["--repo", "owner/repo", "--quick", "--verbose"])

        assert args.repo == "owner/repo"
        assert args.quick is True
        assert args.verbose is True


# =============================================================================
# SINGLE REPO MODE TESTS
# =============================================================================


class TestDiscoverSingleRepo:
    """Tests for discover --repo mode (check specific repository)."""

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_analyzes_specific_repo_when_provided(self, mock_analyze):
        """Should analyze specific repo instead of searching GitHub."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
            artifact_names=["playwright-report"],
            playwright_artifacts=["playwright-report"],
            run_id="123",
            run_url="https://github.com/owner/repo/actions/runs/123",
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo"]):
            with patch("heisenberg.discovery.cli.discover_sources") as mock_discover:
                with pytest.raises(SystemExit) as exc_info:
                    main()

                # Should exit successfully
                assert exc_info.value.code == 0

                # Should NOT call discover_sources (search mode)
                mock_discover.assert_not_called()

                # Should call analyze_source_with_status
                mock_analyze.assert_called_once()
                call_kwargs = mock_analyze.call_args[1]
                assert call_kwargs["repo"] == "owner/repo"

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_exits_zero_for_compatible_repo(self, mock_analyze):
        """Should exit with code 0 when repo is compatible."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
            artifact_names=["blob-report"],
            playwright_artifacts=["blob-report"],
            run_id="123",
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_exits_nonzero_for_incompatible_repo(self, mock_analyze):
        """Should exit with non-zero code when repo is incompatible."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.NO_ARTIFACTS,
            artifact_names=[],
            playwright_artifacts=[],
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_shows_detailed_status_for_single_repo(self, mock_analyze, capsys):
        """Should show detailed status message for single repo check."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=500,
            status=SourceStatus.UNSUPPORTED_FORMAT,
            artifact_names=["html-report"],
            playwright_artifacts=[],
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo"]):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        # Should mention the status reason
        assert "HTML" in captured.out or "unsupported" in captured.out.lower()

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_respects_quick_flag_in_single_repo_mode(self, mock_analyze):
        """Should pass verify_failures based on --quick flag."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo", "--quick"]):
            with pytest.raises(SystemExit):
                main()

        call_kwargs = mock_analyze.call_args[1]
        assert call_kwargs["verify_failures"] is False

    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_json_output_for_single_repo(self, mock_analyze, capsys):
        """Should output JSON when --json flag is used."""
        import json

        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=SourceStatus.COMPATIBLE,
            artifact_names=["blob-report"],
            playwright_artifacts=["blob-report"],
            run_id="123",
            run_url="https://github.com/owner/repo/actions/runs/123",
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo", "--json"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        data = json.loads(captured.out)

        assert data["repo"] == "owner/repo"
        assert data["compatible"] is True
        assert data["status"] == "compatible"


# =============================================================================
# STATUS MESSAGE TESTS
# =============================================================================


class TestStatusMessages:
    """Tests for human-readable status messages in single repo mode."""

    @pytest.mark.parametrize(
        "status,expected_keyword",
        [
            (SourceStatus.COMPATIBLE, "compatible"),
            (SourceStatus.NO_FAILURES, "no failures"),
            (SourceStatus.NO_ARTIFACTS, "no artifacts"),
            (SourceStatus.NO_FAILED_RUNS, "no failed runs"),
            (SourceStatus.UNSUPPORTED_FORMAT, "HTML"),
            (SourceStatus.HAS_ARTIFACTS, "not Playwright"),
        ],
    )
    @patch("heisenberg.discovery.cli.analyze_source_with_status")
    def test_status_messages_contain_reason(self, mock_analyze, status, expected_keyword, capsys):
        """Each status should produce a message explaining the reason."""
        mock_analyze.return_value = ProjectSource(
            repo="owner/repo",
            stars=1000,
            status=status,
        )

        with patch("sys.argv", ["discover", "--repo", "owner/repo"]):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        assert expected_keyword.lower() in captured.out.lower()
