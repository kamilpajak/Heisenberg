# Observations & Future Improvements

## 2026-01-25: Blob Reports Support ✅ IMPLEMENTED

### Problem (SOLVED)
Heisenberg ~~cannot~~ **can now** extract Playwright reports from projects that use **blob reporters** (sharded test runs).

### Technical Details
- Many large projects (e.g., `microsoft/playwright`) use sharded test execution
- Playwright generates "blob reports" for merge-reports workflow
- GitHub Actions artifacts contain: `artifact.zip` → `report-*.zip` → `*.json`
- Heisenberg's `extract_playwright_report()` only looks for JSON files at the first ZIP level

### Evidence
```
# Artifact structure from microsoft/playwright run 21336408770:
artifact.zip
└── report-chromium---bbbdb0f.zip   # <-- nested ZIP not extracted
    └── report.json                  # <-- actual report
```

### Current Code (github_artifacts.py:284-310)
```python
def extract_playwright_report(self, zip_content: bytes) -> dict | None:
    # Only searches first-level JSON files
    json_files = [name for name in zf.namelist() if name.endswith(".json")]
```

### Implementation ✅
Recursive ZIP extraction added in `github_artifacts.py:284-360`:
```python
def extract_playwright_report(self, zip_content: bytes, max_depth: int = 3) -> dict | None:
    # First, try to find JSON files directly (preferred)
    # Second, try JSONL files (Playwright blob report format)
    # If no valid JSON/JSONL found, look for nested ZIP files
    # Recursively extract with depth limit for safety
```

**Tests added:**
- 9 tests in `TestBlobReportExtraction` class (nested ZIP extraction)
- 5 tests in `TestJsonlReportExtraction` class (JSONL format support)

### Important Discovery: Raw Blob Reports ⚠️

Real Playwright blob reports (e.g., from `microsoft/playwright`) contain **protocol events**, not ready-to-use report data:

```json
{"method": "onBegin", "params": {...}}
{"method": "onTestBegin", "params": {...}}
{"method": "onStepBegin", "params": {...}}
```

**This format requires `npx playwright merge-reports` to produce a standard JSON report.**

The current implementation works for:
- ✅ Standard JSON reports (`reporter: [['json', {...}]]`)
- ✅ Pre-merged blob reports (output of `merge-reports`)
- ✅ JSONL files with standard report structure
- ❌ Raw blob reports (protocol events) - need merge step first

### Recommendation for Users
Projects using sharded tests should add a merge step to their CI:
```yaml
- name: Merge blob reports
  run: npx playwright merge-reports --reporter=json ./blob-reports

- name: Upload merged report
  uses: actions/upload-artifact@v4
  with:
    name: playwright-report
    path: merged-report.json
```

### Affected Projects
- microsoft/playwright
- Any project using `reporter: [['blob', { outputFile: '...' }]]`
- Projects with sharded test execution using merge-reports

### Workaround
Users must use projects with direct JSON reporter:
```typescript
// playwright.config.ts
reporter: [['json', { outputFile: 'test-results.json' }]]
```

---

## Future Investigation Needed

### Projects to Test With
- [ ] Find open-source projects using direct JSON reporter (not blob)
- [ ] Cal.com - uses Playwright but E2E workflow may be disabled
- [ ] Smaller projects with simpler CI setup

### Additional Improvements
- [ ] Support for Playwright HTML report parsing
- [ ] Support for blob report merging
- [ ] Better error messages when artifact format is unsupported

---

## 2026-01-25: GitHub Artifacts Availability

### Observation
Most popular open-source projects do NOT upload Playwright JSON reports as GitHub Actions artifacts.

### What Projects Actually Upload
| Project | Artifacts |
|---------|-----------|
| microsoft/playwright | blob-report-*.zip (nested ZIPs) |
| appwrite/appwrite | Docker build artifacts only |
| strapi/strapi | Coverage reports only |
| shadcn-ui/ui | No test artifacts |
| supabase/supabase | No Playwright artifacts |

### Reasons
1. **Storage costs** - JSON reports can be large
2. **Privacy** - Reports may contain sensitive test data
3. **Different workflows** - Many use blob reports for sharding
4. **No need** - Teams use Playwright's HTML reporter locally

### Implication for `fetch-github`
The `fetch-github` command has limited real-world utility because:
- Few projects upload compatible artifacts
- Those that do often use blob reports (not supported)

### Suggested Improvements
1. Add documentation about artifact requirements
2. Provide a sample GitHub workflow that uploads compatible reports
3. Consider supporting HTML report parsing as alternative
4. Add `--list-artifacts` flag to help users debug

### Recommended Testing Approach
For real 1:1 testing, users should:
1. Clone a project with Playwright tests locally
2. Run tests with `--reporter=json`
3. Analyze the local report with `heisenberg analyze`

This bypasses GitHub artifact limitations entirely.

---

## 2026-01-25: Professional Validation Strategy (Expert Analysis)

### Core Problem
Heisenberg relies on a passive "discovery" model - hoping to find compatible artifacts on public repos. This is fundamentally unreliable and leaves the AI analysis engine untested against real-world variance.

### Recommended Approach: "Canary Repository" Model

Instead of searching for compatible projects, **create a dedicated test repository**:

```
Repository: kamilpajak/heisenberg-canary
Purpose: Stable, predictable source of real Playwright failures
```

#### Implementation:
1. **Create `heisenberg-canary` repo** with diverse Playwright tests designed to fail:
   - Timeout scenarios (slow API, missing elements)
   - Selector failures (wrong testid, DOM changes)
   - Assertion failures (incorrect values, missing content)
   - Network failures (API errors, connection refused)
   - Flaky patterns (race conditions, timing issues)

2. **GitHub Actions workflow** (runs daily or on-demand):
   ```yaml
   - name: Run Playwright tests
     run: npx playwright test --reporter=json
     continue-on-error: true

   - name: Upload JSON report
     uses: actions/upload-artifact@v4
     with:
       name: playwright-report  # Compatible with Heisenberg!
       path: test-results.json
   ```

3. **Integration test in Heisenberg CI**:
   ```python
   @pytest.mark.integration
   async def test_fetch_from_canary_repo():
       """Validate fetch-github against live canary repository."""
       report = await client.fetch_latest_report("kamilpajak", "heisenberg-canary")
       assert report is not None
       assert "suites" in report
   ```

### Benefits
- **Predictable**: Always has compatible artifacts
- **Diverse**: Covers all failure types systematically
- **Live**: Real GitHub API, real artifacts, real chaos
- **Demo-ready**: Perfect for documentation and demos
- **Fixture source**: Fresh, authentic test data for unit tests

### Additional Recommendations

#### Quick Wins (Low Effort, High Impact)
1. ~~**Implement blob report support**~~ ✅ DONE - recursive ZIP extraction + JSONL
2. ~~**Add `--list-artifacts` flag**~~ ✅ DONE - helps debug artifact issues
3. **Improve error messages** - guide users to local workflow when fetch fails

#### Medium-Term
1. **Integration test suite** (`pytest.mark.integration`) for real API calls
2. **Re-position README** - promote local `analyze` as primary, `fetch-github` as convenience
3. **HTML report parsing** - many teams only upload HTML reports

#### Long-Term
- **GitHub App** - automatic analysis on workflow completion, zero-config for users
