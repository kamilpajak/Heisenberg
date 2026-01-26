"""Mutmut configuration for filtering mutations.

This file allows advanced filtering of mutations to reduce false positives,
particularly for LLM prompt strings that don't need exact string matching tests.
"""


def pre_mutation(context):
    """Filter out mutations that would generate false positives.

    Args:
        context: Mutmut context with current_source_line and skip attribute.
    """
    line = context.current_source_line

    # Skip LLM prompt-related lines (changing "You are an expert" to "XXu are an expert"
    # shouldn't require exact string matching tests)
    prompt_indicators = [
        "system_prompt",
        "user_prompt",
        "SYSTEM_PROMPT",
        "USER_PROMPT",
        "You are",
        "Analyze the",
        "Given the following",
    ]

    for indicator in prompt_indicators:
        if indicator in line:
            context.skip = True
            return

    # Skip docstrings (triple quotes)
    if '"""' in line or "'''" in line:
        context.skip = True
        return

    # Skip logging statements (changing log messages shouldn't fail tests)
    if "logger." in line or "logging." in line:
        context.skip = True
        return

    # Skip type hints and annotations
    if "-> " in line and ":" in line and "def " not in line:
        context.skip = True
        return
