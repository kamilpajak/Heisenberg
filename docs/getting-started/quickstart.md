# Quick Start

## Analyze a Test Report

```bash
heisenberg analyze path/to/report.json
```

## Freeze a GitHub Actions Run

Download artifacts from a failed GitHub Actions run:

```bash
heisenberg freeze --repo owner/repo --run-id 12345
```

## Example Output

```
=== Root Cause Analysis ===

Test: should display user profile
File: tests/profile.spec.ts:42

Root Cause: Race condition in data loading
The test clicks the profile button before the user data is fully loaded.

Suggested Fix:
Add a wait for the API response before clicking:
  await page.waitForResponse('**/api/user');
```
