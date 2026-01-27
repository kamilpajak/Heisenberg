# Heisenberg Demo Playground - Implementation Plan

> **Status:** In Progress
> **Created:** 2026-01-27
> **Last Updated:** 2026-01-27

## Executive Summary

Build an interactive web playground that demonstrates Heisenberg's AI-powered test failure diagnosis using **real examples from GitHub projects** - not synthetic/curated scenarios. The key innovation is the **"Frozen Snapshots"** architecture that downloads and hosts artifacts locally, avoiding GitHub's 90-day artifact expiration.

## Problem Statement

1. **Hardcoded demos break** - GitHub artifacts expire after 90 days
2. **Synthetic examples lack credibility** - DevOps engineers are skeptical of "perfect" demos
3. **Live discovery is risky** - Rate limits, latency, unpredictable results

## Solution: "Museum of Failures" Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FROZEN SNAPSHOTS PIPELINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. discover_projects.py          [DONE]                        │
│     └── Finds GitHub repos with failed Playwright runs          │
│                                                                 │
│  2. freeze_scenario.py            [DONE - TDD]                  │
│     └── Downloads artifacts, saves locally                      │
│     └── Creates metadata.json with source info                  │
│                                                                 │
│  3. analyze_scenario.py           [TODO]                        │
│     └── Runs Heisenberg on frozen data                          │
│     └── Saves diagnosis.json                                    │
│                                                                 │
│  4. manifest_generator.py         [TODO]                        │
│     └── Aggregates scenarios into manifest.json                 │
│     └── Calculates accuracy stats                               │
│                                                                 │
│  5. validate_scenarios.py         [TODO]                        │
│     └── Checks if scenarios are still valid                     │
│     └── Flags stale/outdated entries                            │
│                                                                 │
│  6. SvelteKit Playground          [TODO]                        │
│     └── Consumes manifest.json                                  │
│     └── Zero API calls, instant load                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Real Projects Over Synthetic

| Aspect | Synthetic | Real GitHub Projects |
|--------|-----------|---------------------|
| Trust | "This is staged" | "I can verify on GitHub" |
| Credibility | Low | High (stars, activity) |
| Edge cases | Missing | Naturally present |
| Maintenance | Must invent bugs | Bugs exist organically |

### Why Frozen Snapshots Over Live Discovery

| Aspect | Live Discovery | Frozen Snapshots |
|--------|---------------|------------------|
| Latency | 30-60+ seconds | Instant (0ms) |
| Reliability | Rate limits, 404s | 100% uptime |
| Consistency | Random results | Curated quality |
| Cost | API calls per visit | One-time download |

### Transparency Builds Trust

Research shows that **acknowledging limitations increases credibility**. Our demo should include:
- Tier 1: Clear root cause identified (showcase strength)
- Tier 2: Complex multi-factor diagnosis (show depth)
- **Tier 3: "Cannot determine" cases** (show honesty)

Display accuracy metrics openly:
```
Accuracy on real GitHub issues: 68% root cause found
26% actionable instrumentation recommendations
6% incorrect diagnosis
```

## Data Structures

### Scenario Directory Structure

```
playground/scenarios/
├── manifest.json                    # Index of all scenarios
└── tryghost-ghost-21395156769/
    ├── metadata.json                # Source info, stars, dates
    ├── report.json                  # Playwright report (LOCAL COPY)
    ├── trace.zip                    # Playwright traces (LOCAL COPY)
    ├── logs.txt                     # Docker/CI logs (optional)
    └── diagnosis.json               # Heisenberg output (PRE-COMPUTED)
```

### manifest.json Schema

```json
{
  "generated_at": "2026-01-27T12:00:00Z",
  "scenarios": [
    {
      "id": "tryghost-ghost-21395156769",
      "display_name": "E2E Timeout in Ghost CMS",
      "source": {
        "repo": "TryGhost/Ghost",
        "repo_url": "https://github.com/TryGhost/Ghost",
        "stars": 51700,
        "captured_at": "2026-01-27",
        "original_run_id": "21395156769"
      },
      "failure_type": "timeout",
      "difficulty_tier": 1,
      "assets": {
        "report": "tryghost-ghost-21395156769/report.json",
        "trace": "tryghost-ghost-21395156769/trace.zip",
        "diagnosis": "tryghost-ghost-21395156769/diagnosis.json"
      },
      "validation": {
        "heisenberg_result": "root_cause_found",
        "confidence_score": 0.87
      }
    }
  ],
  "stats": {
    "total_scenarios": 5,
    "root_cause_found": 3,
    "recommendations_only": 1,
    "incorrect": 1,
    "last_refresh": "2026-01-27"
  }
}
```

### metadata.json Schema (per scenario)

```json
{
  "repo": "TryGhost/Ghost",
  "repo_url": "https://github.com/TryGhost/Ghost",
  "stars": 51700,
  "run_id": 21395156769,
  "run_url": "https://github.com/TryGhost/Ghost/actions/runs/21395156769",
  "captured_at": "2026-01-27T12:00:00Z",
  "artifact_names": ["playwright-report", "e2e-coverage"]
}
```

## Implementation Status

### Completed

- [x] `scripts/discover_projects.py` - Finds GitHub repos with Playwright artifacts
- [x] `src/heisenberg/freeze_scenario.py` - Downloads and saves artifacts locally (TDD, 24 tests)
- [x] `src/heisenberg/github_artifacts.py` - GitHub API client for artifacts

### In Progress

- [x] CLI wrapper for freeze_scenario (`heisenberg freeze <repo>`) - **Done, 18 tests**
- [x] `analyze_scenario.py` - Run Heisenberg analysis on frozen data - **Done, 24 tests**
- [x] CLI wrapper for analyze_scenario (`heisenberg analyze-scenario <dir>`)

### TODO
- [x] `manifest_generator.py` - Generate manifest.json from scenarios - **Done, 27 tests**
- [x] CLI wrapper for manifest generator (`heisenberg generate-manifest <dir>`)
- [x] `validate_scenarios.py` - Check scenario freshness - **Done, 28 tests**
- [x] CLI wrapper for validator (`heisenberg validate-scenarios <dir>`)
- [x] GitHub Action for periodic refresh - `.github/workflows/refresh-demo-scenarios.yml`
- [ ] SvelteKit playground frontend

## CLI Commands

### Implemented

```bash
# Discover candidate projects
python scripts/discover_projects.py --limit 30 --output candidates.json

# Freeze a specific scenario (downloads artifacts locally)
heisenberg freeze -r TryGhost/Ghost --run-id 21395156769 --output ./scenarios

# Freeze latest failed run
heisenberg freeze -r formkit/auto-animate --output ./scenarios

# Analyze frozen scenario (runs AI diagnosis, saves diagnosis.json)
heisenberg analyze-scenario ./scenarios/tryghost-ghost-21395156769 -p google

# Generate manifest from all analyzed scenarios
heisenberg generate-manifest ./scenarios -o manifest.json

# Validate all scenarios (check freshness and completeness)
heisenberg validate-scenarios ./scenarios --max-age 90 --json
```

### Planned

```bash
# GitHub Action will automate: validate → discover → freeze → analyze → manifest
```

## Candidate Projects (from discover_projects.py)

Last scan: 2026-01-27

| Repo | Stars | Artifacts | Notes |
|------|-------|-----------|-------|
| TryGhost/Ghost | 51,700 | e2e-coverage | Popular CMS |
| formkit/auto-animate | 13,739 | playwright-report | Clean artifacts |
| evcc-io/evcc | 6,078 | playwright-report | Active project |
| lukevella/rallly | 4,924 | playwright-report | Scheduling app |
| siemens/ix | 318 | blob-report x4 | Visual testing |
| Scille/parsec-cloud | 293 | blob-report + playwright | Security focus |

## Frontend Architecture (SvelteKit)

```
heisenberg-playground/
├── src/
│   ├── routes/
│   │   ├── +page.svelte              # Main playground
│   │   └── +layout.svelte            # Shell with nav
│   ├── lib/
│   │   ├── components/
│   │   │   ├── ScenarioPicker.svelte # Scenario selection
│   │   │   ├── Terminal.svelte       # xterm.js wrapper
│   │   │   ├── TraceViewer.svelte    # Playwright trace embed
│   │   │   ├── DiagnosisCard.svelte  # AI analysis display
│   │   │   └── SourceBadge.svelte    # GitHub link + stars
│   │   └── stores/
│   │       └── scenario.ts           # Active scenario state
├── static/
│   ├── scenarios/                    # Frozen snapshots
│   └── manifest.json                 # Scenario index
└── package.json
```

### Key UI Elements

1. **Scenario Picker** - List of real GitHub projects with stars, dates
2. **Terminal View** (xterm.js) - Typewriter effect for CLI output
3. **Trace Viewer** - Embedded Playwright trace (if available)
4. **Diagnosis Card** - AI analysis with confidence score
5. **Source Badge** - Link to original GitHub issue/PR
6. **CTA Button** - "Try on your own tests → pip install heisenberg"

## Research Insights

From Perplexity deep research (2026-01-27):

1. **Interactive demos have 20x higher engagement** than video (67% CTR vs 3.21%)
2. **46% of developers distrust AI tools** - transparency about limitations builds trust
3. **Bottom-up adoption** - convince individual engineers, not managers
4. **Real examples >> synthetic** - developers can verify claims themselves
5. **Successful patterns**: Sentry (error→code linking), Copilot (specific tasks), Playwright (community)

## Refresh Strategy

### Implemented: `.github/workflows/refresh-demo-scenarios.yml`

**Schedule:** Every Monday at 6 AM UTC (with manual trigger option)

**Jobs:**

1. **validate** - Check existing scenarios for staleness/completeness
2. **discover** - Find new GitHub projects with Playwright artifacts
3. **freeze-and-analyze** - Download artifacts, run AI diagnosis, generate manifest
4. **commit** - Push changes to repository
5. **cleanup-stale** - Remove scenarios older than 90 days

**Required Secrets:**
- `GITHUB_TOKEN` - For GitHub API access (automatic)
- `GOOGLE_API_KEY` - For AI analysis (Gemini)

**Manual Trigger Options:**
- `max_new_scenarios` - Limit new scenarios per run (default: 3)
- `force_refresh` - Force refresh even if no stale scenarios

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first "aha" | < 30 seconds | User testing |
| Scenario load time | < 100ms | Performance monitoring |
| Accuracy display | Visible above fold | UI review |
| GitHub verification | 1 click away | UX review |
| CLI install clicks | Track conversions | Analytics |

## Related Files

- `scripts/discover_projects.py` - Project discovery script
- `src/heisenberg/freeze_scenario.py` - Artifact freezer (24 tests)
- `src/heisenberg/analyze_scenario.py` - Scenario analyzer (24 tests)
- `src/heisenberg/manifest_generator.py` - Manifest generator (27 tests)
- `src/heisenberg/validate_scenarios.py` - Scenario validator (28 tests)
- `src/heisenberg/github_artifacts.py` - GitHub API client
- `src/heisenberg/cli/commands.py` - CLI command handlers
- `tests/test_freeze_scenario.py` - Freezer tests
- `tests/test_analyze_scenario.py` - Analyzer tests
- `tests/test_manifest_generator.py` - Manifest generator tests
- `tests/test_validate_scenarios.py` - Validator tests
- `tests/test_cli_freeze.py` - CLI freeze tests (18 tests)
- `.github/workflows/refresh-demo-scenarios.yml` - Automated refresh workflow

## Related Obsidian Notes

- [[Heisenberg - Product Concept]]
- [[Heisenberg - Pre-Launch Checklist]]
- [[Heisenberg - Open Source Promotion Plan]]

---

## Changelog

### 2026-01-27
- Initial plan created
- `freeze_scenario.py` implemented with TDD (24 tests passing)
- Discovered 7 compatible GitHub projects for demo
- CLI wrapper `heisenberg freeze` implemented with TDD (18 tests passing)
- `analyze_scenario.py` implemented with TDD (24 tests passing)
- CLI wrapper `heisenberg analyze-scenario` implemented
- `manifest_generator.py` implemented with TDD (27 tests passing)
- CLI wrapper `heisenberg generate-manifest` implemented
- `validate_scenarios.py` implemented with TDD (28 tests passing)
- CLI wrapper `heisenberg validate-scenarios` implemented
- GitHub Action `refresh-demo-scenarios.yml` created for automated weekly refresh
- **Known limitation**: Blob reports require `--merge-blobs` (not yet supported in freeze)
