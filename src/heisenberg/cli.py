"""Command-line interface for Heisenberg.

This module provides the main entry point for the CLI.
The actual implementation is in the cli package:
- cli/parsers.py: Argument parsing
- cli/formatters.py: Output formatting
- cli/github_fetch.py: GitHub artifact fetching
- cli/commands.py: Command handlers
"""

from __future__ import annotations

import sys

from heisenberg.cli import main

if __name__ == "__main__":
    sys.exit(main())
