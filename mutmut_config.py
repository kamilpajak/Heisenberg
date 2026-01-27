"""Mutmut configuration for filtering mutations.

This file filters line-level mutations to reduce false positives.
File-level exclusions are handled in setup.cfg via do_not_mutate.
"""


def pre_mutation(context):
    """Filter out mutations that would generate false positives.

    Args:
        context: Mutmut context with current_source_line and skip attribute.
    """
    line = context.current_source_line

    # Skip patterns that don't need exact string matching tests
    skip_patterns = [
        # Docstrings
        '"""',
        "'''",
        # Logging (changing log messages shouldn't fail tests)
        "logger.",
        "logging.",
        # LLM prompts (exact wording doesn't matter for functionality)
        "You are",
        "Analyze the",
        "Given the following",
        "system_prompt",
        "user_prompt",
        "SYSTEM_PROMPT",
        "USER_PROMPT",
    ]

    if any(pattern in line for pattern in skip_patterns):
        context.skip = True
