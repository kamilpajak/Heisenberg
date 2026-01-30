"""Output formatters for Heisenberg CLI."""

from __future__ import annotations

import json


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def format_json_output(result, ai_result) -> str:
    """Format result as JSON."""
    flaky_detected = any(
        getattr(t, "retry_count", 0) > 0 or t.status == "flaky" for t in result.report.failed_tests
    )
    data = {
        "has_failures": result.has_failures,
        "flaky_detected": flaky_detected,
        "summary": result.summary,
        "failed_tests_count": len(result.report.failed_tests),
        "failed_tests": [
            {"name": t.full_name, "file": t.file, "status": t.status, "error": t.error_summary}
            for t in result.report.failed_tests
        ],
    }
    if ai_result:
        data["ai_diagnosis"] = {
            "root_cause": ai_result.diagnosis.root_cause,
            "evidence": ai_result.diagnosis.evidence,
            "suggested_fix": ai_result.diagnosis.suggested_fix,
            "confidence": ai_result.diagnosis.confidence.value,
            "tokens_used": ai_result.total_tokens,
            "estimated_cost": ai_result.estimated_cost,
        }
    return json.dumps(data, indent=2)


def format_output(args, result, ai_result) -> str:
    """Format output based on requested format."""
    output_format = getattr(args, "output_format", "text")
    if output_format == "github-comment":
        output = result.to_markdown()
        if ai_result:
            output += "\n\n" + ai_result.to_markdown()
        return output
    elif output_format == "json":
        return format_json_output(result, ai_result)
    return format_text_output(result, ai_result)


def format_junit_json(report, ai_result) -> str:
    """Format JUnit report as JSON."""
    data = {
        "has_failures": report.total_failed > 0,
        "summary": {
            "total": report.total_tests,
            "passed": report.total_passed,
            "failed": report.total_failed,
            "errors": report.total_errors,
            "skipped": report.total_skipped,
        },
        "failed_tests": [
            {
                "name": tc.name,
                "classname": tc.classname,
                "status": tc.status,
                "error": tc.failure_message,
            }
            for tc in report.failed_tests
        ],
    }
    if ai_result:
        data["ai_diagnosis"] = {
            "root_cause": ai_result.diagnosis.root_cause,
            "evidence": ai_result.diagnosis.evidence,
            "suggested_fix": ai_result.diagnosis.suggested_fix,
            "confidence": ai_result.diagnosis.confidence.value,
        }
    return json.dumps(data, indent=2)


def format_junit_text(report, ai_result=None) -> str:
    """Format JUnit report as plain text."""
    lines = [
        "Heisenberg Test Analysis (JUnit)",
        "=" * 40,
        "",
        f"Summary: {report.total_passed} passed, {report.total_failed} failed, "
        f"{report.total_skipped} skipped",
        "",
    ]

    if report.failed_tests:
        lines.extend(["Failed Tests:", "-" * 40])
        for tc in report.failed_tests:
            lines.append(f"  - {tc.classname} > {tc.name}")
            lines.append(f"    Status: {tc.status}")
            if tc.failure_message:
                msg = tc.failure_message
                if len(msg) > 100:
                    msg = msg[:100] + "..."
                lines.append(f"    Error: {msg}")
            lines.append("")

    if ai_result:
        lines.extend(format_ai_diagnosis_section(ai_result))

    return "\n".join(lines)


def format_failed_tests_section(failed_tests: list) -> list[str]:
    """Format failed tests section."""
    lines = ["Failed Tests:", "-" * 40]
    for test in failed_tests:
        lines.append(f"  - {test.full_name}")
        lines.append(f"    File: {test.file}")
        lines.append(f"    Status: {test.status}")
        if test.errors:
            error_msg = test.errors[0].message
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            lines.append(f"    Error: {error_msg}")
        lines.append("")
    return lines


def format_container_logs_section(container_logs: dict) -> list[str]:
    """Format container logs section."""
    lines = ["Backend Logs:", "-" * 40]
    for name, logs in container_logs.items():
        lines.append(f"  [{name}]")
        for entry in logs.entries[:10]:
            lines.append(f"    {entry}")
        if len(logs.entries) > 10:
            lines.append(f"    ... and {len(logs.entries) - 10} more entries")
        lines.append("")
    return lines


def format_ai_diagnosis_section(ai_result) -> list[str]:
    """Format AI diagnosis section."""
    lines = ["AI Diagnosis:", "-" * 40]
    lines.append(f"  Root Cause: {ai_result.diagnosis.root_cause}")
    lines.append("")
    if ai_result.diagnosis.evidence:
        lines.append("  Evidence:")
        lines.extend(f"    - {item}" for item in ai_result.diagnosis.evidence)
        lines.append("")
    lines.append(f"  Suggested Fix: {ai_result.diagnosis.suggested_fix}")
    lines.append("")
    lines.append(f"  Confidence: {ai_result.diagnosis.confidence.value}")
    if ai_result.diagnosis.confidence_explanation:
        lines.append(f"  ({ai_result.diagnosis.confidence_explanation})")
    lines.append("")
    lines.append(f"  Tokens: {ai_result.total_tokens} | Cost: ${ai_result.estimated_cost:.4f}")
    lines.append("")
    return lines


def format_text_output(result, ai_result=None) -> str:
    """Format result as plain text."""
    lines = ["Heisenberg Test Analysis", "=" * 40, "", f"Summary: {result.summary}", ""]

    if result.has_failures:
        lines.extend(format_failed_tests_section(result.report.failed_tests))

    if result.container_logs:
        lines.extend(format_container_logs_section(result.container_logs))

    if ai_result:
        lines.extend(format_ai_diagnosis_section(ai_result))

    return "\n".join(lines)
