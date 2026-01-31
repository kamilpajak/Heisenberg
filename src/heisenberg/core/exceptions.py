"""Shared exceptions for the Heisenberg package."""


class HtmlReportNotSupported(Exception):
    """Exception raised when artifact contains HTML report instead of JSON.

    Playwright HTML reports cannot be parsed programmatically.
    Users need to configure JSON reporter in their Playwright config.
    """

    def __init__(self) -> None:
        super().__init__(
            "Artifact contains HTML report, not JSON. "
            "Heisenberg requires Playwright JSON reporter. "
            "Add to playwright.config.ts: reporter: [['json', { outputFile: 'results.json' }]]"
        )
