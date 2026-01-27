"""GitHub artifact fetching for Heisenberg CLI."""

from __future__ import annotations

import io
import sys
import zipfile

from heisenberg.cli.formatters import format_size


async def _resolve_run_id(client, owner: str, repo: str, run_id: int | None) -> int | None:
    """Get the latest failed run ID if none is provided.

    Args:
        client: GitHubArtifactClient instance.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific run ID.

    Returns:
        Run ID to use, or None if no failed runs found.
    """
    if run_id is not None:
        return run_id

    runs = await client.list_workflow_runs(owner, repo)
    failed_runs = [r for r in runs if r.conclusion == "failure"]

    if not failed_runs:
        return None

    return failed_runs[0].id


async def fetch_report_from_run(client, owner: str, repo: str, run_id: int, artifact_name: str):
    """Fetch Playwright report from a specific workflow run."""
    artifacts = await client.get_artifacts(owner, repo, run_id=run_id)
    matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

    if not matching:
        return None

    zip_data = await client.download_artifact(owner, repo, matching[0].id)
    return client.extract_playwright_report(zip_data)


async def fetch_and_process_job_logs(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
) -> str | None:
    """Fetch and process job logs from GitHub Actions.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.

    Returns:
        Formatted job logs context string, or None if no logs available.
    """
    from heisenberg.integrations.github_artifacts import GitHubArtifactClient
    from heisenberg.integrations.github_logs import GitHubLogsFetcher
    from heisenberg.parsers.job_logs import JobLogsProcessor

    client = GitHubArtifactClient(token=token)
    actual_run_id = await _resolve_run_id(client, owner, repo, run_id)

    if actual_run_id is None:
        return None

    print(f"Fetching job logs for run {actual_run_id}...", file=sys.stderr)

    fetcher = GitHubLogsFetcher()
    logs_by_job = fetcher.fetch_logs_for_run(f"{owner}/{repo}", str(actual_run_id))

    if not logs_by_job:
        print("No job logs found.", file=sys.stderr)
        return None

    processor = JobLogsProcessor()
    all_snippets = []

    for _job_name, log_content in logs_by_job.items():
        snippets = processor.extract_snippets(log_content)
        all_snippets.extend(snippets)

    if not all_snippets:
        print("No error snippets found in job logs.", file=sys.stderr)
        return None

    print(f"Found {len(all_snippets)} relevant log snippet(s).", file=sys.stderr)
    return processor.format_for_prompt(all_snippets)


async def fetch_and_analyze_screenshots(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> str | None:
    """Fetch and analyze screenshots from Playwright artifacts.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        artifact_name: Pattern to match artifact name.

    Returns:
        Formatted screenshot analysis string, or None if no screenshots.
    """
    from heisenberg.integrations.github_artifacts import GitHubArtifactClient
    from heisenberg.parsers.screenshots import (
        ScreenshotAnalyzer,
        extract_screenshots_from_artifact,
        format_screenshots_for_prompt,
    )

    try:
        client = GitHubArtifactClient(token=token)
        actual_run_id = await _resolve_run_id(client, owner, repo, run_id)

        if actual_run_id is None:
            return None

        artifacts = await client.get_artifacts(owner, repo, run_id=actual_run_id)
        matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

        if not matching:
            return None

        all_screenshots = []
        for artifact in matching[:1]:  # Only first matching artifact
            print(f"Extracting screenshots from: {artifact.name}...", file=sys.stderr)
            zip_data = await client.download_artifact(owner, repo, artifact.id)
            screenshots = extract_screenshots_from_artifact(zip_data)
            all_screenshots.extend(screenshots)

        if not all_screenshots:
            print("No screenshots found in artifacts.", file=sys.stderr)
            return None

        print(f"Found {len(all_screenshots)} screenshot(s). Analyzing...", file=sys.stderr)

        analyzer = ScreenshotAnalyzer(provider="google")
        analyzed = analyzer.analyze_batch(all_screenshots, max_screenshots=5)

        return format_screenshots_for_prompt(analyzed)
    except Exception as e:
        print(f"Failed to fetch screenshots: {e}", file=sys.stderr)
        return None


async def fetch_and_analyze_traces(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> str | None:
    """Fetch and analyze Playwright traces from artifacts.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        artifact_name: Pattern to match artifact name.

    Returns:
        Formatted trace analysis string, or None if no traces.
    """
    from heisenberg.integrations.github_artifacts import GitHubArtifactClient
    from heisenberg.parsers.traces import (
        TraceAnalyzer,
        extract_trace_from_artifact,
        format_trace_for_prompt,
    )

    try:
        client = GitHubArtifactClient(token=token)
        actual_run_id = await _resolve_run_id(client, owner, repo, run_id)

        if actual_run_id is None:
            return None

        artifacts = await client.get_artifacts(owner, repo, run_id=actual_run_id)
        matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

        if not matching:
            return None

        all_traces = []
        zip_data = None
        for artifact in matching[:1]:  # Only first matching artifact
            print(f"Extracting traces from: {artifact.name}...", file=sys.stderr)
            zip_data = await client.download_artifact(owner, repo, artifact.id)
            traces = extract_trace_from_artifact(zip_data)
            all_traces.extend(traces)

        if not all_traces or not zip_data:
            print("No trace files found in artifacts.", file=sys.stderr)
            return None

        print(f"Found {len(all_traces)} trace file(s). Analyzing...", file=sys.stderr)

        analyzer = TraceAnalyzer()
        analyzed_traces = []

        try:
            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as outer_zip:
                for file_info in outer_zip.filelist:
                    name = file_info.filename.lower()
                    if not name.endswith("trace.zip"):
                        continue

                    path_parts = file_info.filename.split("/")
                    test_name = path_parts[-2] if len(path_parts) > 1 else "unknown"
                    file_path = next(
                        (p for p in path_parts if ".spec." in p or ".test." in p),
                        "unknown-file",
                    )

                    trace_zip_data = outer_zip.read(file_info.filename)
                    trace_ctx = analyzer.analyze(trace_zip_data, test_name, file_path)
                    analyzed_traces.append(trace_ctx)

                    if len(analyzed_traces) >= 5:
                        break
        except Exception as e:
            print(f"Warning: Error analyzing traces: {e}", file=sys.stderr)

        if not analyzed_traces:
            return None

        return format_trace_for_prompt(analyzed_traces)
    except Exception as e:
        print(f"Failed to fetch traces: {e}", file=sys.stderr)
        return None


async def list_artifacts(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    output=None,
) -> int:
    """List artifacts for debugging purposes.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        output: Output stream (defaults to stdout).

    Returns:
        0 on success, 1 on error.
    """
    from heisenberg.integrations.github_artifacts import GitHubArtifactClient

    if output is None:
        output = sys.stdout

    try:
        client = GitHubArtifactClient(token=token)

        if run_id is None:
            runs = await client.list_workflow_runs(owner, repo)
            failed_runs = [r for r in runs if r.conclusion == "failure"]
            if not failed_runs:
                output.write("No failed workflow runs found.\n")
                output.write(
                    "\nTip: For local reports, use: heisenberg analyze --report <path-to-json>\n"
                )
                return 0
            run_id = failed_runs[0].id
            output.write(f"Using latest failed run: {run_id}\n")
            output.write(f"  URL: {failed_runs[0].html_url}\n\n")

        artifacts = await client.get_artifacts(owner, repo, run_id=run_id)

        if not artifacts:
            output.write(f"No artifacts found for run {run_id}.\n")
            return 0

        output.write(f"Artifacts for run {run_id}:\n")
        output.write("-" * 60 + "\n")

        for artifact in artifacts:
            expired_marker = " [EXPIRED]" if artifact.expired else ""
            size = format_size(artifact.size_in_bytes)
            output.write(f"  {artifact.name:<40} {size:>10}{expired_marker}\n")

        output.write("-" * 60 + "\n")
        output.write(f"Total: {len(artifacts)} artifact(s)\n")

        output.write("\nTip: Use --artifact-name <pattern> to filter artifacts.\n")
        output.write("     Example: --artifact-name playwright\n")

        return 0
    except Exception as e:
        print(f"Error listing artifacts: {e}", file=sys.stderr)
        return 1


async def fetch_and_merge_blobs(
    token: str,
    owner: str,
    repo: str,
    run_id: int | None,
    artifact_name: str,
) -> dict | None:
    """Fetch blob artifacts and merge them into a JSON report.

    Args:
        token: GitHub token.
        owner: Repository owner.
        repo: Repository name.
        run_id: Optional specific workflow run ID.
        artifact_name: Pattern to match artifact name.

    Returns:
        Merged JSON report or None.
    """
    from heisenberg.integrations.github_artifacts import GitHubArtifactClient
    from heisenberg.utils.merging import BlobMergeError, extract_blob_zips, merge_blob_reports

    client = GitHubArtifactClient(token=token)

    if run_id is None:
        runs = await client.list_workflow_runs(owner, repo)
        failed_runs = [r for r in runs if r.conclusion == "failure"]
        if not failed_runs:
            return None
        run_id = failed_runs[0].id
        print(f"Using latest failed run: {run_id}", file=sys.stderr)

    artifacts = await client.get_artifacts(owner, repo, run_id=run_id)
    matching = [a for a in artifacts if artifact_name.lower() in a.name.lower()]

    if not matching:
        return None

    all_blob_zips = []
    for artifact in matching:
        print(f"Downloading artifact: {artifact.name}...", file=sys.stderr)
        zip_data = await client.download_artifact(owner, repo, artifact.id)
        blob_zips = extract_blob_zips(zip_data)
        all_blob_zips.extend(blob_zips)

    if not all_blob_zips:
        raise BlobMergeError(
            f"No blob ZIP files found in artifacts. "
            f"Found {len(matching)} artifact(s) but no report-*.zip files inside."
        )

    print(f"Merging {len(all_blob_zips)} blob report(s)...", file=sys.stderr)
    return await merge_blob_reports(blob_zips=all_blob_zips)
