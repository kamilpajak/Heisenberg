# Discovery UI Redesign Plan

## Problem Statement

Current UX issues:
1. No visibility into search phase (4 queries to GitHub)
2. All repos displayed equally (compatible buried in noise)
3. Redundant output: scan shows lines, then summary repeats
4. No live counters ("how many compatible found?")
5. Confusing flags: `--no-cache` vs `--fresh` vs `--verify`

## New UX Concept: "Headline Discovery"

**Core principle:** Users care about COMPATIBLE repos. Everything else is noise filtering.

### Target Output

```
Searching GitHub for Playwright repos...

  Query 1/4: playwright "upload-artifact"... 23 repos
  Query 2/4: "blob-report" upload-artifact... 15 repos (+8 new)
  Query 3/4: "playwright-report" actions... 12 repos (+3)
  Query 4/4: "blob-report" extension:yml... 18 repos (+5)

Found 39 candidates -> analyzing 21 (12 quarantined, 6 below 100 stars)

  [check] microsoft/playwright    81.5k stars   blob-report    [2.1s]
  [check] vercel/next.js          125k stars    playwright-report

================================================================
  2 COMPATIBLE
    + microsoft/playwright              81,500 stars
    + vercel/next.js                   125,000 stars

  Filtered: 7 no artifacts, 5 no runs, 4 not playwright, 3 passing
================================================================
```

## Architecture

### Event-Based System

Decouple business logic from display with typed events:

```python
# Search Phase Events
SearchStarted(total_queries: int)
QueryCompleted(query_index: int, query_preview: str, repos_found: int, new_repos: int)
SearchCompleted(total_candidates: int, quarantine_skipped: int, stars_filtered: int, to_analyze: int)

# Analysis Phase Events
AnalysisStarted(repo: str, stars: int, index: int, total: int)
AnalysisProgress(repo: str, stage: str)
AnalysisCompleted(repo: str, stars: int, status: SourceStatus, artifact_name: str | None, ...)

# Final Event
DiscoveryCompleted(results: list[ProjectSource], stats: dict[str, int])
```

### Display Modes

| Mode | Search | Non-compatible | Compatible | Summary |
|------|--------|----------------|------------|---------|
| Default | Query progress | Silent | Immediate pop | Grouped stats |
| --verbose | Full details | All shown | Highlighted | Full list |
| --quiet | Silent | Silent | Silent | Only summary |
| --json | Silent | Silent | Silent | JSON to stdout |

## Implementation Phases

### Phase 1: Event System (events.py - NEW)
- Create event dataclasses
- Define DiscoveryEvent union type
- Define EventHandler callable type

### Phase 2: Display Component (display.py - NEW)
- Create DiscoveryDisplay class
- Implement event handlers
- Support verbose/quiet modes

### Phase 3: Service Layer (service.py - MODIFY)
- Add `on_event: EventHandler | None` parameter
- Emit events from search and analysis phases
- Remove old show_progress/on_progress (breaking change OK)

### Phase 4: CLI (cli.py - REWRITE)
- New flags: --verbose/-v, --quiet/-q, --json, --stars
- Wire up DiscoveryDisplay
- Remove old print_summary logic

### Phase 5: Cleanup (ui.py - SIMPLIFY)
- Keep only save_results() and format helpers
- Remove deprecated Rich progress code

## New CLI Arguments

```
heisenberg discover [OPTIONS]

Filtering:
  --stars MIN     Minimum stars (default: 100)
  --limit N       Max repos to analyze (default: 30)

Caching (mutually exclusive):
  --fresh         Ignore quarantine cache
  --no-cache      Disable all caching

Verification:
  --verify        Download artifacts to confirm failures

Output:
  --verbose, -v   Show all repos during analysis
  --quiet, -q     Only show final summary
  --json          Output JSON to stdout
  --output FILE   Save results to JSON file
```

## File Changes Summary

| File | Action | Risk |
|------|--------|------|
| events.py | NEW | Low |
| display.py | NEW | Low |
| service.py | MODIFY | Medium |
| cli.py | REWRITE | Medium |
| ui.py | SIMPLIFY | Low |

Estimated: ~400-500 lines of new/modified code.
