"""Report handler registry for discovering and selecting handlers."""

from __future__ import annotations

import io
from zipfile import ZipFile

from .base import ReportHandler


class ReportRegistry:
    """Registry for report handlers.

    The registry maintains a list of handlers and can identify
    which handler should be used for a given report ZIP file.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._handlers: list[ReportHandler] = []

    @property
    def handlers(self) -> list[ReportHandler]:
        """Return the list of registered handlers."""
        return self._handlers.copy()

    def register(self, handler: ReportHandler) -> None:
        """Register a handler with the registry.

        Args:
            handler: The handler to register.
        """
        self._handlers.append(handler)

    def identify(self, zip_content: bytes) -> ReportHandler | None:
        """Identify which handler can process the given ZIP content.

        Args:
            zip_content: The raw bytes of the ZIP file.

        Returns:
            The first handler that can process the content, or None.
        """
        with ZipFile(io.BytesIO(zip_content)) as zf:
            for handler in self._handlers:
                if handler.can_handle(zf):
                    return handler
        return None


def get_default_registry() -> ReportRegistry:
    """Create a registry with all default handlers registered.

    Returns:
        A ReportRegistry with Playwright and other handlers.
    """
    from .handlers.playwright import PlaywrightHandler

    registry = ReportRegistry()
    registry.register(PlaywrightHandler())
    return registry
