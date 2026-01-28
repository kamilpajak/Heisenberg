
import { Manifest, FullCaseData, ConfidenceLevel } from './types';

// Helper to get a date relative to now (for demo purposes)
const getRecentDate = (daysAgo: number) => {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return date.toISOString().split('T')[0];
};

export const MOCK_MANIFEST: Manifest = {
  stats: {
    total: 843,
    high: 612,
    medium: 185,
    low: 46
  },
  cases: [
    {
      id: "enso-org-enso",
      repoOwner: "enso-org",
      repoName: "enso",
      stars: 7433,
      snapshotDate: getRecentDate(2),
      confidence: ConfidenceLevel.HIGH,
      rootCausePreview: "Race condition in websocket connection initialization during high load.",
      githubActionsUrl: "https://github.com/enso-org/enso/actions/runs/123456789"
    },
    {
      id: "microsoft-playwright",
      repoOwner: "microsoft",
      repoName: "playwright",
      stars: 56000,
      snapshotDate: getRecentDate(5),
      confidence: ConfidenceLevel.HIGH,
      rootCausePreview: "Timeout waiting for network idle state after form submission.",
      githubActionsUrl: "https://github.com/microsoft/playwright/actions"
    },
    {
      id: "scille-parsec-cloud",
      repoOwner: "Scille",
      repoName: "parsec-cloud",
      stars: 293,
      snapshotDate: getRecentDate(12),
      confidence: ConfidenceLevel.LOW,
      rootCausePreview: "Ambiguous selector resolution for the login button component.",
      githubActionsUrl: "https://github.com/Scille/parsec-cloud/actions"
    },
    {
      id: "vercel-nextjs",
      repoOwner: "vercel",
      repoName: "next.js",
      stars: 114000,
      snapshotDate: getRecentDate(1),
      confidence: ConfidenceLevel.HIGH,
      rootCausePreview: "Hydration mismatch error in server-side rendered comments component.",
      githubActionsUrl: "https://github.com/vercel/next.js/actions"
    },
    {
      id: "remix-run-remix",
      repoOwner: "remix-run",
      repoName: "remix",
      stars: 25000,
      snapshotDate: getRecentDate(8),
      confidence: ConfidenceLevel.MEDIUM,
      rootCausePreview: "Flaky navigation assertion due to optimistic UI updates.",
      githubActionsUrl: "https://github.com/remix-run/remix/actions"
    },
    {
      id: "react-hook-form",
      repoOwner: "react-hook-form",
      repoName: "react-hook-form",
      stars: 38000,
      snapshotDate: getRecentDate(20),
      confidence: ConfidenceLevel.HIGH,
      rootCausePreview: "Incorrect validation trigger timing on async default values.",
      githubActionsUrl: "https://github.com/react-hook-form/react-hook-form/actions"
    }
  ]
};

// Default empty values for new fields to prevent crashes on other cases
const DEFAULT_EXTRAS = {
  dataSources: [],
  timeline: [],
};

const ENSO_DATA: FullCaseData = {
  id: "enso-org-enso",
  summary: MOCK_MANIFEST.cases[0],
  metadata: {
    repoUrl: "https://github.com/enso-org/enso",
    githubActionsUrl: "https://github.com/enso-org/enso/actions/runs/123456789",
    language: "Rust/TypeScript",
    framework: "Playwright",
    snapshotDate: getRecentDate(2),
    stars: 7433
  },
  diagnosis: {
    confidence: ConfidenceLevel.HIGH,
    verdict: "WebSocket Initialization Race Condition",
    confidenceScore: 92,
    rootCause: "The test fails due to a race condition where the application attempts to send a WebSocket message before the connection is fully established.",
    reasoning: "The stack trace indicates a 'WebSocket is not open: readyState 0 (CONNECTING)' error. The logs show the connect() call happens 5ms before the failure.",
    recommendations: [
      {
        description: "Await the WebSocket 'open' event explicitly before attempting to send messages.",
        codeSnippet: "await new Promise(resolve => ws.addEventListener('open', resolve));"
      }
    ]
  },
  report: {
    totalTests: 450,
    failedTests: 1,
    failures: [
      {
        testName: "Should connect to language server",
        filePath: "app/ide-desktop/lib/content/src/index.spec.ts",
        errorMessage: "Error: WebSocket is not open: readyState 0 (CONNECTING)",
        stackTrace: `Error: WebSocket is not open: readyState 0 (CONNECTING)\n    at WebSocket.send`
      }
    ]
  },
  ...DEFAULT_EXTRAS,
  // Added multi-file fix data for Enso
  fix: {
    summary: "WebSocket sends message before connection is ready. Fix requires await in client.ts and timeout config in playwright.config.ts.",
    diffs: [
      {
        fileName: "client.ts",
        isRootCause: true,
        language: "typescript",
        originalContent: `class Client {
    connect() {
        this.ws = new WebSocket(url);
    }
    
    send(msg) {
        this.ws.send(JSON.stringify(msg));
    }
}`,
        modifiedContent: `class Client {
    connect() {
        this.ws = new WebSocket(url);
        this.ready = new Promise(resolve => {
            this.ws.addEventListener('open', resolve);
        });
    }
    
    async send(msg) {
        await this.ready;
        this.ws.send(JSON.stringify(msg));
    }
}`
      },
      {
        fileName: "playwright.config.ts",
        language: "typescript",
        originalContent: `export default defineConfig({
  timeout: 30000,
  retries: 2,
  use: {
    trace: 'on-first-retry',
  },
});`,
        modifiedContent: `export default defineConfig({
  timeout: 45000, // Increased for WS handshake
  retries: 2,
  use: {
    trace: 'on-first-retry',
  },
});`
      }
    ]
  }
};

const PLAYWRIGHT_DATA: FullCaseData = {
    id: "microsoft-playwright",
    summary: MOCK_MANIFEST.cases[1],
    metadata: {
      repoUrl: "https://github.com/microsoft/playwright",
      githubActionsUrl: "https://github.com/microsoft/playwright/actions",
      language: "TypeScript",
      framework: "Playwright",
      snapshotDate: getRecentDate(5),
      stars: 56000
    },
    diagnosis: {
      confidence: ConfidenceLevel.HIGH,
      verdict: "Network Idle Timeout",
      confidenceScore: 98,
      rootCause: "Assertion error due to timing mismatch between UI update and network idle check.",
      reasoning: "The test asserts text content immediately after clicking submit. While the network request finishes, the React DOM has not yet hydrated the new state.",
      recommendations: [
        {
          description: "Await the specific UI element state instead of network idle.",
          codeSnippet: "await expect(page.locator('.success-message')).toBeVisible();"
        }
      ]
    },
    report: {
      totalTests: 2500,
      failedTests: 1,
      failures: [
        {
            testName: "Form submission handling",
            filePath: "tests/forms.spec.ts",
            errorMessage: "Error: expect(received).toContain(expected)\nExpected substring: 'Success'",
            stackTrace: `Error: expect(received).toContain(expected)\n    at tests/forms.spec.ts:102:25`
        }
      ]
    },
    ...DEFAULT_EXTRAS
}

const PARSEC_DATA: FullCaseData = {
  id: "scille-parsec-cloud",
  summary: MOCK_MANIFEST.cases[2],
  metadata: {
    repoUrl: "https://github.com/Scille/parsec-cloud",
    githubActionsUrl: "https://github.com/Scille/parsec-cloud/actions",
    language: "Python/React",
    framework: "Playwright",
    snapshotDate: getRecentDate(12),
    stars: 293
  },
  diagnosis: {
    confidence: ConfidenceLevel.LOW,
    verdict: "Ambiguous Selector Resolution",
    confidenceScore: 45,
    rootCause: "Potential ambiguous selector resolution or dynamic class name changes affecting the login button.",
    reasoning: "The error is a generic 'Timeout 30000ms exceeded while waiting for selector'. The AI analyzed the DOM snapshot and found multiple elements matching '.btn-primary'.",
    recommendations: [
      {
        description: "Use a more specific selector, such as a data-testid attribute.",
        codeSnippet: "await page.getByTestId('login-submit-btn').click();"
      }
    ]
  },
  report: {
    totalTests: 120,
    failedTests: 2,
    failures: [
      {
        testName: "User Login Flow",
        filePath: "tests/e2e/auth.spec.ts",
        errorMessage: "TimeoutError: page.click: Timeout 30000ms exceeded.",
        stackTrace: `TimeoutError: page.click: Timeout 30000ms exceeded.\n    at LoginPage.submit`
      }
    ]
  },
  ...DEFAULT_EXTRAS
};

// --- REACT HOOK FORM (THE HERO CASE) ---
const HOOK_FORM_DATA: FullCaseData = {
  id: "react-hook-form",
  summary: MOCK_MANIFEST.cases[5],
  metadata: {
    repoUrl: "https://github.com/react-hook-form/react-hook-form",
    githubActionsUrl: "https://github.com/react-hook-form/react-hook-form/actions",
    language: "TypeScript",
    framework: "React",
    snapshotDate: getRecentDate(20),
    stars: 38000
  },
  diagnosis: {
    confidence: ConfidenceLevel.HIGH,
    confidenceScore: 85,
    verdict: "Async Validation Race Condition",
    rootCause: "We detected a race condition. Playwright Trace shows submit clicked at 0.4s, but Console Logs indicate async validation resolved at 0.6s. The test expects validation to block submission, but the useEffect hook fired late.",
    reasoning: "Trace alignment shows the click event triggering before the validation promise resolved.",
    recommendations: []
  },
  report: {
    totalTests: 1250,
    failedTests: 1,
    failures: [
      {
        testName: "should validate async default values correctly",
        filePath: "src/__tests__/useForm.test.tsx",
        errorMessage: "Error: expect(element).toBeVisible() \nReceived: hidden",
        stackTrace: "Error: expect(element).toBeVisible()..."
      }
    ]
  },
  dataSources: [
    { id: 'trace', name: 'Playwright Trace', status: 'active', iconType: 'trace', insight: 'Submit click at 400ms' },
    { id: 'console', name: 'Console Logs', status: 'active', iconType: 'log', insight: 'Async resolved at 600ms' },
    { id: 'network', name: 'Network Logs', status: 'neutral', iconType: 'network', insight: 'GET /schema 200 OK' },
    { id: 'screens', name: 'Screenshots', status: 'neutral', iconType: 'image', insight: 'No visual regression' },
    { id: 'docker', name: 'Docker Logs', status: 'missing', iconType: 'container', insight: 'Unavailable' },
    { id: 'actions', name: 'GitHub Actions', status: 'missing', iconType: 'server', insight: 'Unavailable' },
  ],
  confidenceGap: {
    message: "To increase confidence to ~95%, provide:",
    missingSources: [
      "Docker container logs (rule out resource starvation)",
      "GitHub Actions logs (check runner environment)"
    ]
  },
  timeline: [
    { time: "0ms", label: "Test Start", type: "trace" },
    { time: "400ms", label: "click(submit)", type: "trace" },
    { time: "450ms", label: "GET /validation-schema 200", type: "network" },
    { time: "600ms", label: "Async validation resolved", type: "console", isAnomaly: true },
    { time: "5000ms", label: "expect(error).toBeVisible() FAIL", type: "error" }
  ],
  fix: {
    summary: "Race condition: api.ts returns data before useForm.ts finishes validation setup.",
    diffs: [
      {
        fileName: "useForm.ts",
        isRootCause: true,
        language: "typescript",
        originalContent: `const onSubmit = () => {
  if (validationSchema) {
    validate(values);
  }
  handleSubmit(values);
};`,
        modifiedContent: `const onSubmit = async () => {
  if (validationSchema) {
    await validate(values);
  }
  handleSubmit(values);
};`
      }
    ]
  }
};

const NEXTJS_DATA = { ...ENSO_DATA, id: "vercel-nextjs", summary: MOCK_MANIFEST.cases[3], metadata: { ...ENSO_DATA.metadata, repoOwner: "vercel", repoName: "next.js", stars: 114000 } };
const REMIX_DATA = { ...PLAYWRIGHT_DATA, id: "remix-run-remix", summary: MOCK_MANIFEST.cases[4], metadata: { ...PLAYWRIGHT_DATA.metadata, repoOwner: "remix-run", repoName: "remix", stars: 25000 } };

export const CASE_DATA_MAP: Record<string, FullCaseData> = {
  "enso-org-enso": ENSO_DATA,
  "scille-parsec-cloud": PARSEC_DATA,
  "microsoft-playwright": PLAYWRIGHT_DATA,
  "vercel-nextjs": NEXTJS_DATA,
  "remix-run-remix": REMIX_DATA,
  "react-hook-form": HOOK_FORM_DATA
};
