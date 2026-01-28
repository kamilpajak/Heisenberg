# Heisenberg Playground

Interactive demo showcasing Heisenberg's AI-powered root cause analysis for flaky tests.

## Run Locally

**Prerequisites:** Node.js 18+

```bash
pnpm install
pnpm dev
```

Open http://localhost:3000

## Structure

```
playground/
├── public/
│   └── demo-cases/       # Frozen test data from real repos
├── components/           # Reusable UI components
├── pages/               # Dashboard and CaseDetail views
├── services/            # Data fetching with adapters
└── types.ts             # TypeScript interfaces
```

## Demo Data

The `public/demo-cases/` folder contains frozen snapshots from real GitHub repositories with actual Playwright test failures analyzed by Heisenberg.

To refresh demo data:
```bash
heisenberg freeze --repo owner/repo --output playground/public/demo-cases
```
