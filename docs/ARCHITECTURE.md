# Heisenberg Architecture

## System Overview

```mermaid
flowchart TB
    subgraph Input["📥 Input Sources"]
        CLI["CLI Commands"]
        GHA["GitHub Action"]
    end

    subgraph Fetchers["🔍 Data Fetchers"]
        GAF["GitHub Artifacts<br/>Fetcher"]
        GLF["GitHub Logs<br/>Fetcher"]
        DLF["Docker Logs<br/>Fetcher"]
    end

    subgraph Observation["👁️ Observation Points"]
        direction TB
        subgraph TestReport["Test Reports"]
            PW["Playwright JSON"]
            JU["JUnit XML"]
        end
        subgraph Traces["Playwright Traces"]
            CON["Console Logs<br/>(JS errors, warnings)"]
            NET["Network Requests<br/>(failed API calls)"]
            ACT["Action Timeline<br/>(clicks, navigations)"]
        end
        subgraph Visual["Visual Evidence"]
            SS["Screenshots<br/>(failure state)"]
        end
        subgraph Logs["Execution Logs"]
            JOB["Job Logs<br/>(CI errors)"]
            DOC["Container Logs<br/>(backend errors)"]
        end
    end

    subgraph Parsers["⚙️ Parsers & Transformers"]
        PP["Playwright<br/>Parser"]
        JP["JUnit<br/>Parser"]
        TA["Trace<br/>Analyzer"]
        SA["Screenshot<br/>Analyzer"]
        JLP["Job Logs<br/>Processor"]
        LC["Log<br/>Compressor"]
    end

    subgraph Unified["🔄 Unified Model"]
        UM["UnifiedTestRun"]
        UF["UnifiedFailure[]"]
    end

    subgraph AI["🤖 AI Analysis"]
        PB["Prompt<br/>Builder"]
        LLM["LLM Client<br/>(Claude/OpenAI/Gemini)"]
        DP["Diagnosis<br/>Parser"]
    end

    subgraph Output["📤 Output"]
        DIAG["Diagnosis"]
        GHC["GitHub PR<br/>Comment"]
        JSON["JSON/Text<br/>Output"]
    end

    %% Input flow
    CLI --> GAF
    CLI --> DLF
    GHA --> GAF

    %% Fetcher to observation
    GAF --> PW
    GAF --> JU
    GAF --> CON
    GAF --> NET
    GAF --> ACT
    GAF --> SS
    GLF --> JOB
    DLF --> DOC

    %% Observation to parsers
    PW --> PP
    JU --> JP
    CON --> TA
    NET --> TA
    ACT --> TA
    SS --> SA
    JOB --> JLP
    DOC --> LC

    %% Parsers to unified model
    PP --> UM
    JP --> UM
    UM --> UF

    %% All context to prompt builder
    UF --> PB
    TA --> PB
    SA --> PB
    JLP --> PB
    LC --> PB

    %% AI pipeline
    PB --> LLM
    LLM --> DP
    DP --> DIAG

    %% Output
    DIAG --> GHC
    DIAG --> JSON

    %% Styling
    classDef input fill:#e1f5fe,stroke:#01579b
    classDef observation fill:#fff3e0,stroke:#e65100
    classDef parser fill:#f3e5f5,stroke:#7b1fa2
    classDef unified fill:#e8f5e9,stroke:#2e7d32
    classDef ai fill:#fce4ec,stroke:#c2185b
    classDef output fill:#e0f2f1,stroke:#00695c

    class CLI,GHA input
    class PW,JU,CON,NET,ACT,SS,JOB,DOC observation
    class PP,JP,TA,SA,JLP,LC parser
    class UM,UF unified
    class PB,LLM,DP ai
    class DIAG,GHC,JSON output
```

## Observation Points Detail

```mermaid
flowchart LR
    subgraph Frontend["Frontend Observations"]
        direction TB
        T1["🎭 Playwright Traces"]
        T1a["├─ Console: JS errors/warnings"]
        T1b["├─ Network: Failed API calls"]
        T1c["├─ Actions: Click/navigation timeline"]
        T1d["└─ DOM: Snapshots at failure"]

        T2["📸 Screenshots"]
        T2a["└─ Visual state at failure moment"]
    end

    subgraph Backend["Backend Observations"]
        direction TB
        T3["📋 Job Logs"]
        T3a["├─ CI/CD errors"]
        T3b["├─ Test runner output"]
        T3c["└─ Build failures"]

        T4["🐳 Container Logs"]
        T4a["├─ API server errors"]
        T4b["├─ Database errors"]
        T4c["└─ Service timeouts"]
    end

    subgraph TestData["Test Data"]
        direction TB
        T5["📊 Test Reports"]
        T5a["├─ Failed test names"]
        T5b["├─ Error messages"]
        T5c["├─ Stack traces"]
        T5d["└─ Test duration"]
    end

    Frontend --> AI["🤖 AI Correlation"]
    Backend --> AI
    TestData --> AI
    AI --> D["📝 Root Cause Diagnosis"]
```

## Data Flow Timeline

```mermaid
sequenceDiagram
    participant U as User/CI
    participant CLI as CLI
    participant GH as GitHub API
    participant P as Parsers
    participant UM as Unified Model
    participant AI as LLM
    participant O as Output

    U->>CLI: heisenberg analyze/fetch-github

    alt fetch-github
        CLI->>GH: Get workflow run
        GH-->>CLI: Run metadata
        CLI->>GH: Download artifacts
        GH-->>CLI: ZIP files
    end

    rect rgb(255, 243, 224)
        Note over P: Observation Point Extraction
        CLI->>P: Parse test report
        CLI->>P: Extract traces (console, network, actions)
        CLI->>P: Extract screenshots
        CLI->>P: Process job logs
        CLI->>P: Compress container logs
    end

    P->>UM: Transform to UnifiedTestRun
    UM->>AI: Build analysis prompt

    rect rgb(252, 228, 236)
        Note over AI: AI Analysis
        AI->>AI: Correlate all evidence
        AI->>AI: Identify root cause
        AI->>AI: Generate fix suggestion
    end

    AI-->>O: Structured Diagnosis
    O-->>U: PR Comment / JSON / Text
```

## Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **CLI** | `cli/commands.py` | Entry point, orchestration |
| **GitHub Artifacts** | `github_artifacts.py` | Download & extract artifacts |
| **Playwright Parser** | `playwright_parser.py` | Parse JSON reports |
| **JUnit Parser** | `junit_parser.py` | Parse XML reports |
| **Trace Analyzer** | `trace_analyzer.py` | Extract console/network/actions |
| **Screenshot Analyzer** | `screenshot_analyzer.py` | Vision LLM analysis |
| **Job Logs Processor** | `job_logs_processor.py` | Filter relevant CI logs |
| **Log Compressor** | `log_compressor.py` | Smart log filtering |
| **Unified Model** | `unified_model.py` | Framework-agnostic representation |
| **Prompt Builder** | `prompt_builder.py` | Construct LLM prompts |
| **LLM Client** | `llm_client.py` | Claude/OpenAI/Gemini calls |
| **Diagnosis Parser** | `diagnosis.py` | Parse LLM response |
| **AI Analyzer** | `ai_analyzer.py` | Orchestrate AI analysis |

## Observation Points Summary

| Source | Data Type | Purpose |
|--------|-----------|---------|
| **Playwright Traces** | Console logs | JS errors, React warnings |
| | Network requests | Failed API calls, timeouts |
| | Action timeline | User interaction sequence |
| **Screenshots** | Images | Visual state at failure |
| **Job Logs** | Text | CI/CD errors, test output |
| **Container Logs** | Text | Backend errors, DB issues |
| **Test Reports** | JSON/XML | Error messages, stack traces |
