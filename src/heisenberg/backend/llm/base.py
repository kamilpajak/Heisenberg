"""Base class for LLM providers.

.. deprecated::
    This module is deprecated. Use :mod:`heisenberg.llm.providers.base` instead.
"""

from __future__ import annotations

import warnings

from heisenberg.llm.providers.base import LLMProvider

__all__ = ["LLMProvider"]

warnings.warn(
    "heisenberg.backend.llm.base is deprecated. Use heisenberg.llm.providers.base instead.",
    DeprecationWarning,
    stacklevel=2,
)
