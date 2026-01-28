import {
  Manifest,
  CaseSummary,
  FullCaseData,
  CaseMetadata,
  Diagnosis,
  TestReport,
  TestFailure,
  ConfidenceLevel,
} from '../types';

// === Raw JSON Types (from frozen files) ===

interface RawManifestScenario {
  id: string;
  display_name: string;
  source: {
    repo: string;
    repo_url: string;
    stars: number;
    captured_at: string;
    original_run_id: number;
  };
  assets: {
    report: string;
    diagnosis: string;
  };
  validation: {
    status: string;
    confidence: string;
    root_cause: string;
    analyzed_at: string;
  };
}

interface RawManifest {
  generated_at: string;
  scenarios: RawManifestScenario[];
  stats: {
    total_scenarios: number;
    high_confidence: number;
    medium_confidence: number;
    low_confidence: number;
    pending: number;
  };
}

interface RawMetadata {
  repo: string;
  repo_url: string;
  stars: number;
  run_id: number;
  run_url: string;
  captured_at: string;
  artifact_names: string[];
  report_type: string;
  visual_only: boolean;
}

interface RawDiagnosis {
  repo: string;
  run_id: number;
  diagnosis: {
    root_cause: string;
    evidence: string[];
    suggested_fix: string;
    confidence: string;
    confidence_explanation: string;
  };
  tokens: {
    input: number;
    output: number;
    total: number;
  };
  provider: string;
  model: string;
  analyzed_at: string;
}

interface RawPlaywrightReport {
  suites: Array<{
    title: string;
    specs: Array<{
      title: string;
      tests: Array<{
        status: string;
        results: Array<{
          status: string;
          duration: number;
          errors: Array<{ message?: string; stack?: string }>;
        }>;
      }>;
    }>;
  }>;
}

// === Adapters ===

const mapConfidence = (raw: string): ConfidenceLevel => {
  const upper = raw.toUpperCase();
  if (upper === 'HIGH') return ConfidenceLevel.HIGH;
  if (upper === 'MEDIUM') return ConfidenceLevel.MEDIUM;
  return ConfidenceLevel.LOW;
};

const mapManifestToTypes = (raw: RawManifest): Manifest => ({
  cases: raw.scenarios.map((s): CaseSummary => {
    const [owner, name] = s.source.repo.split('/');
    return {
      id: s.id,
      repoOwner: owner || 'Unknown',
      repoName: name || s.source.repo,
      stars: s.source.stars,
      snapshotDate: s.source.captured_at.split('T')[0],
      confidence: mapConfidence(s.validation.confidence),
      rootCausePreview: s.validation.root_cause.slice(0, 200) + (s.validation.root_cause.length > 200 ? '...' : ''),
      githubActionsUrl: `${s.source.repo_url}/actions/runs/${s.source.original_run_id}`,
    };
  }),
  stats: {
    total: raw.stats.total_scenarios,
    high: raw.stats.high_confidence,
    medium: raw.stats.medium_confidence,
    low: raw.stats.low_confidence,
  },
});

const mapMetadataToTypes = (raw: RawMetadata): CaseMetadata => ({
  repoUrl: raw.repo_url,
  githubActionsUrl: raw.run_url,
  language: 'TypeScript', // Not in raw data, default
  framework: 'Playwright',
  snapshotDate: raw.captured_at.split('T')[0],
  stars: raw.stars,
});

const mapDiagnosisToTypes = (raw: RawDiagnosis): Diagnosis => ({
  rootCause: raw.diagnosis.root_cause,
  confidence: mapConfidence(raw.diagnosis.confidence),
  reasoning: raw.diagnosis.confidence_explanation,
  recommendations: [
    {
      description: raw.diagnosis.suggested_fix,
    },
  ],
});

const mapReportToTypes = (raw: RawPlaywrightReport): TestReport => {
  const failures: TestFailure[] = [];
  let totalTests = 0;
  let failedTests = 0;

  for (const suite of raw.suites || []) {
    for (const spec of suite.specs || []) {
      for (const test of spec.tests || []) {
        totalTests++;
        for (const result of test.results || []) {
          if (result.status === 'failed' || result.status === 'timedOut') {
            failedTests++;
            for (const error of result.errors || []) {
              failures.push({
                testName: spec.title || 'Unknown Test',
                filePath: suite.title || 'Unknown Suite',
                errorMessage: error.message || 'No error message',
                stackTrace: error.stack || '',
              });
            }
          }
        }
      }
    }
  }

  return {
    totalTests,
    failedTests,
    failures,
  };
};

// === Public API ===

export const fetchManifest = async (): Promise<Manifest> => {
  try {
    const response = await fetch('/demo-cases/manifest.json');
    if (!response.ok) {
      throw new Error(`Failed to fetch manifest: ${response.statusText}`);
    }
    const raw: RawManifest = await response.json();
    return mapManifestToTypes(raw);
  } catch (error) {
    console.error('Error fetching manifest:', error);
    return { cases: [], stats: { total: 0, high: 0, medium: 0, low: 0 } };
  }
};

export const fetchCaseData = async (caseId: string): Promise<FullCaseData | null> => {
  try {
    const basePath = `/demo-cases/${caseId}`;
    const [metadataRes, diagnosisRes, reportRes] = await Promise.all([
      fetch(`${basePath}/metadata.json`),
      fetch(`${basePath}/diagnosis.json`),
      fetch(`${basePath}/report.json`),
    ]);

    if (!metadataRes.ok || !diagnosisRes.ok || !reportRes.ok) {
      console.warn(`Incomplete data for case ${caseId}`);
      return null;
    }

    const rawMetadata: RawMetadata = await metadataRes.json();
    const rawDiagnosis: RawDiagnosis = await diagnosisRes.json();
    const rawReport: RawPlaywrightReport = await reportRes.json();

    const metadata = mapMetadataToTypes(rawMetadata);
    const diagnosis = mapDiagnosisToTypes(rawDiagnosis);
    const report = mapReportToTypes(rawReport);

    const [owner, name] = rawMetadata.repo.split('/');
    const summary: CaseSummary = {
      id: caseId,
      repoOwner: owner || 'Unknown',
      repoName: name || 'Unknown',
      stars: metadata.stars,
      snapshotDate: metadata.snapshotDate,
      confidence: diagnosis.confidence,
      rootCausePreview: diagnosis.rootCause.slice(0, 200),
      githubActionsUrl: metadata.githubActionsUrl,
    };

    return {
      id: caseId,
      summary,
      metadata,
      diagnosis,
      report,
      dataSources: [],
      timeline: [],
      fix: undefined,
    };
  } catch (error) {
    console.error(`Error fetching case data for ${caseId}:`, error);
    return null;
  }
};
