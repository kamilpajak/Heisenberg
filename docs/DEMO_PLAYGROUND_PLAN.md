# Heisenberg Demo Playground - Implementation Plan

> **Status:** Complete (Backend Pipeline)
> **Created:** 2026-01-27
> **Last Updated:** 2026-01-28

## Executive Summary

Build an interactive web playground that demonstrates Heisenberg's AI-powered test failure diagnosis using **real examples from GitHub projects** - not synthetic/curated cases. The key innovation is the **"Frozen Snapshots"** architecture that downloads and hosts artifacts locally, avoiding GitHub's 90-day artifact expiration.

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
│  1. playground/discover.py        [DONE]                        │
│     └── Finds GitHub repos with failed Playwright runs          │
│                                                                 │
│  2. playground/freeze.py          [DONE]                        │
│     └── Downloads artifacts, saves locally                      │
│     └── Creates metadata.json with source info                  │
│                                                                 │
│  3. playground/analyze.py         [DONE]                        │
│     └── Runs Heisenberg on frozen data                          │
│     └── Saves diagnosis.json                                    │
│                                                                 │
│  4. playground/manifest.py        [DONE]                        │
│     └── Aggregates cases into manifest.json                     │
│     └── Calculates accuracy stats                               │
│                                                                 │
│  5. playground/validate.py        [DONE]                        │
│     └── Checks if cases are still valid                         │
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

### Case Directory Structure

```
playground/cases/
├── manifest.json                    # Index of all cases
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

### metadata.json Schema (per case)

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

- [x] `src/heisenberg/playground/discover.py` - Finds GitHub repos with Playwright artifacts
- [x] `src/heisenberg/playground/freeze.py` - Downloads and saves artifacts locally
- [x] `src/heisenberg/playground/analyze.py` - Runs AI analysis on frozen data
- [x] `src/heisenberg/playground/manifest.py` - Generates manifest.json from cases
- [x] `src/heisenberg/playground/validate.py` - Checks case freshness
- [x] `src/heisenberg/integrations/github_artifacts.py` - GitHub API client for artifacts
- [x] CLI wrapper `heisenberg freeze`
- [x] CLI wrapper `heisenberg analyze-case`
- [x] CLI wrapper `heisenberg generate-manifest`
- [x] CLI wrapper `heisenberg validate-cases`
- [x] GitHub Action `.github/workflows/refresh-demo-cases.yml`

### TODO

- [ ] SvelteKit playground frontend

## CLI Commands

### Implemented

```bash
# Freeze a specific case (downloads artifacts locally)
heisenberg freeze -r TryGhost/Ghost --run-id 21395156769 --output ./playground/cases

# Freeze latest failed run
heisenberg freeze -r formkit/auto-animate --output ./playground/cases

# Analyze frozen case (runs AI diagnosis, saves diagnosis.json)
heisenberg analyze-case ./playground/cases/tryghost-ghost-21395156769 -p google

# Generate manifest from all analyzed cases
heisenberg generate-manifest ./playground/cases -o manifest.json

# Validate all cases (check freshness and completeness)
heisenberg validate-cases ./playground/cases --max-age 90 --json
```

### Planned

```bash
# GitHub Action will automate: validate → discover → freeze → analyze → manifest
```

## Candidate Projects (from discover)

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
│   │   │   ├── CasePicker.svelte     # Case selection
│   │   │   ├── Terminal.svelte       # xterm.js wrapper
│   │   │   ├── TraceViewer.svelte    # Playwright trace embed
│   │   │   ├── DiagnosisCard.svelte  # AI analysis display
│   │   │   └── SourceBadge.svelte    # GitHub link + stars
│   │   └── stores/
│   │       └── case.ts               # Active case state
├── static/
│   ├── cases/                        # Frozen snapshots
│   └── manifest.json                 # Case index
└── package.json
```

### Key UI Elements

1. **Case Picker** - List of real GitHub projects with stars, dates
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

### Implemented: `.github/workflows/refresh-demo-cases.yml`

**Schedule:** Every Monday at 6 AM UTC (with manual trigger option)

**Jobs:**

1. **validate** - Check existing cases for staleness/completeness
2. **discover** - Find new GitHub projects with Playwright artifacts
3. **freeze-and-analyze** - Download artifacts, run AI diagnosis, generate manifest
4. **commit** - Push changes to repository
5. **cleanup-stale** - Remove cases older than 90 days

**Required Secrets:**
- `GITHUB_TOKEN` - For GitHub API access (automatic)
- `GOOGLE_API_KEY` - For AI analysis (Gemini)

**Manual Trigger Options:**
- `max_new_cases` - Limit new cases per run (default: 3)
- `force_refresh` - Force refresh even if no stale cases

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to first "aha" | < 30 seconds | User testing |
| Case load time | < 100ms | Performance monitoring |
| Accuracy display | Visible above fold | UI review |
| GitHub verification | 1 click away | UX review |
| CLI install clicks | Track conversions | Analytics |

## Related Files

- `src/heisenberg/playground/discover.py` - Project discovery
- `src/heisenberg/playground/freeze.py` - Artifact freezer
- `src/heisenberg/playground/analyze.py` - Case analyzer
- `src/heisenberg/playground/manifest.py` - Manifest generator
- `src/heisenberg/playground/validate.py` - Case validator
- `src/heisenberg/integrations/github_artifacts.py` - GitHub API client
- `src/heisenberg/cli/commands.py` - CLI command handlers
- `tests/test_freeze_case.py` - Freezer tests
- `tests/test_analyze_case.py` - Analyzer tests
- `tests/test_manifest_generator.py` - Manifest generator tests
- `tests/test_validate_cases.py` - Validator tests
- `tests/test_cli_freeze.py` - CLI freeze tests
- `.github/workflows/refresh-demo-cases.yml` - Automated refresh workflow

## Related Obsidian Notes

- [[Heisenberg - Product Concept]]
- [[Heisenberg - Pre-Launch Checklist]]
- [[Heisenberg - Open Source Promotion Plan]]

---

## Changelog

### 2026-01-28
- Updated plan to reflect actual implementation
- Changed terminology from "scenarios" to "cases" throughout
- Updated file paths to match actual structure (`src/heisenberg/playground/`)
- Updated CLI command names (`analyze-case`, `validate-cases`)
- Updated workflow name (`refresh-demo-cases.yml`)
- Marked all pipeline components as DONE

### 2026-01-27
- Initial plan created
- All pipeline components implemented
- GitHub Action created for automated weekly refresh
- **Known limitation**: Blob reports require `--merge-blobs` (not yet supported in freeze)
