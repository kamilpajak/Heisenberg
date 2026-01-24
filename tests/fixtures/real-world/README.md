# Real-World Playwright Report Fixtures

This directory contains real Playwright JSON reports from open-source projects,
used to validate Heisenberg's ability to analyze actual test failures.

## Sources

### Cal.com (`calcom/`)

**Repository**: https://github.com/calcom/cal.com
**Playwright Config**: `apps/web/playwright.config.ts`

Fixtures collected:
- `timeout-booking.json` - Booking flow timeout failure
- `selector-calendar.json` - Calendar component selector not found
- `assertion-availability.json` - Availability check assertion failure

### Grafana (`grafana/`)

**Repository**: https://github.com/grafana/grafana
**Playwright Config**: `e2e/playwright.config.ts`

Fixtures collected:
- `network-api.json` - API request failure
- `flaky-dashboard.json` - Intermittent dashboard loading failure

## Collection Process

1. Fork/clone the repository
2. Configure JSON reporter in `playwright.config.ts`:
   ```typescript
   reporter: [['json', { outputFile: 'test-results.json' }]]
   ```
3. Run tests or introduce controlled failures
4. Copy the JSON report to appropriate subdirectory
5. Rename to indicate failure type

## Failure Types

| Type | Description | Example Error |
|------|-------------|---------------|
| `timeout` | Test exceeded timeout | "Test timeout of 30000ms exceeded" |
| `selector` | Element not found | "Locator: getByTestId('x') Expected: visible" |
| `assertion` | Assertion failed | "expect(received).toBe(expected)" |
| `network` | API/network error | "net::ERR_CONNECTION_REFUSED" |
| `flaky` | Intermittent failure | Same test passes on retry |

## Adding New Fixtures

1. Create subdirectory for new project: `mkdir projectname/`
2. Add fixtures with descriptive names: `failure-type-context.json`
3. Update this README with source information
4. Ensure fixtures contain real, anonymized data (no secrets/PII)
