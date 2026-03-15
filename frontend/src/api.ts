import type { DiseaseSummary, DiseaseReport, GenomeSummary } from "./types";

const API_BASE = "/api";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  listDiseases: () => fetchJson<DiseaseSummary[]>("/diseases"),
  listGenomes: () => fetchJson<GenomeSummary[]>("/genomes"),
  queryDisease: (person: string, diseaseId: string) =>
    fetchJson<DiseaseReport>(`/query/${person}/${diseaseId}`),
};
