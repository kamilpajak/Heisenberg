import { MOCK_MANIFEST, CASE_DATA_MAP } from '../constants';
import { Manifest, FullCaseData } from '../types';

// Simulates fetching manifest.json
export const fetchManifest = async (): Promise<Manifest> => {
  // In production: const response = await fetch('/playground/demo-cases/manifest.json');
  // return await response.json();
  
  // Artificial delay for realism
  return new Promise((resolve) => {
    setTimeout(() => resolve(MOCK_MANIFEST), 400); 
  });
};

// Simulates fetching case specific files
export const fetchCaseData = async (caseId: string): Promise<FullCaseData | null> => {
  // In production, we would fetch metadata.json, diagnosis.json, and report.json concurrently
  
  return new Promise((resolve) => {
    setTimeout(() => {
      const data = CASE_DATA_MAP[caseId];
      resolve(data || null);
    }, 600);
  });
};