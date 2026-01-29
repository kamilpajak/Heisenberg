
export enum ConfidenceLevel {
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW'
}

export interface CaseSummary {
  id: string;
  repoOwner: string;
  repoName: string;
  stars: number;
  snapshotDate: string;
  confidence: ConfidenceLevel;
  rootCausePreview: string;
  githubActionsUrl: string;
}

export interface Manifest {
  cases: CaseSummary[];
  stats: {
    total: number;
    high: number;
    medium: number;
    low: number;
  };
}

export interface CaseMetadata {
  repoUrl: string;
  githubActionsUrl: string;
  language: string;
  framework: string;
  snapshotDate: string;
  stars: number;
}

export interface Recommendation {
  description: string;
  codeSnippet?: string;
}

export interface Diagnosis {
  rootCause: string;
  verdict?: string; // Short "Headline" verdict
  confidence: ConfidenceLevel;
  confidenceScore?: number; // Numeric score 0-100
  reasoning: string;
  recommendations: Recommendation[];
}

export interface TestFailure {
  testName: string;
  filePath: string;
  errorMessage: string;
  stackTrace: string;
}

export interface TestReport {
  totalTests: number;
  failedTests: number;
  failures: TestFailure[];
}

// New Types for Detailed View
export type DataSourceStatus = 'active' | 'neutral' | 'missing';

export interface DataSource {
  id: string;
  name: string;
  status: DataSourceStatus;
  iconType: 'trace' | 'log' | 'network' | 'image' | 'container' | 'server';
  insight: string;
}

export interface TimelineEvent {
  time: string; // e.g. "400ms"
  label: string;
  type: 'trace' | 'network' | 'console' | 'error' | 'info';
  isAnomaly?: boolean;
}

export interface CodeDiff {
  fileName: string;
  language: string;
  originalContent: string;
  modifiedContent: string;
  isRootCause?: boolean;
}

export interface ConfigChange {
  settingName: string;
  oldValue: string;
  newValue: string;
  reason: string;
}

export interface FixSolution {
  summary?: string; // Narrative explanation
  diffs?: CodeDiff[];
  configChanges?: ConfigChange[];
}

export interface FullCaseData {
  id: string;
  summary: CaseSummary;
  metadata: CaseMetadata;
  diagnosis: Diagnosis;
  report: TestReport;
  // New Fields
  dataSources: DataSource[];
  confidenceGap?: {
    missingSources: string[];
    message: string;
  };
  timeline: TimelineEvent[];
  fix?: FixSolution;
}
