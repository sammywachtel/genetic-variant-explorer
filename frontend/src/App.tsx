import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import CategorySection from "./CategorySection";
import type { DiseaseSummary, DiseaseReport, GenomeSummary, MergedCategory } from "./types";
import "./App.css";

const MAX_COMPARE = 3;

function mergeReports(reports: DiseaseReport[]): MergedCategory[] {
  if (reports.length === 0) return [];

  // All reports share the same category/variant structure for a given disease
  return reports[0].categories.map((baseCat, ci) => ({
    name: baseCat.name,
    description: baseCat.description,
    variants: baseCat.variant_results.map((baseVr, vi) => ({
      base: baseVr,
      people: reports.map((r) => ({
        person: r.person,
        vr: r.categories[ci].variant_results[vi],
      })),
    })),
    regions: baseCat.region_results.map((baseRr, ri) => ({
      base: baseRr,
      people: reports.map((r) => ({
        person: r.person,
        rr: r.categories[ci].region_results[ri],
      })),
    })),
    personInterpretations: reports.map((r) => ({
      person: r.person,
      interpretations: r.categories[ci].interpretations,
    })),
  }));
}

export default function App() {
  const [diseases, setDiseases] = useState<DiseaseSummary[]>([]);
  const [genomes, setGenomes] = useState<GenomeSummary[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<string>("");
  const [selectedGenomes, setSelectedGenomes] = useState<string[]>([]);
  const [reports, setReports] = useState<DiseaseReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load diseases and genomes on mount
  useEffect(() => {
    Promise.all([api.listDiseases(), api.listGenomes()])
      .then(([d, g]) => {
        setDiseases(d);
        setGenomes(g);
        if (d.length === 1) setSelectedDisease(d[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  // Query when disease + at least one genome selected
  useEffect(() => {
    if (!selectedDisease || selectedGenomes.length === 0) {
      setReports([]);
      return;
    }
    setLoading(true);
    setError(null);

    Promise.all(
      selectedGenomes.map((g) => api.queryDisease(g, selectedDisease))
    )
      .then((r) => setReports(r))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedDisease, JSON.stringify(selectedGenomes)]);

  const merged = useMemo(() => mergeReports(reports), [reports]);
  const isComparing = selectedGenomes.length > 1;
  const selectedDiseaseInfo = diseases.find((d) => d.id === selectedDisease);

  function toggleGenome(name: string) {
    setSelectedGenomes((prev) => {
      if (prev.includes(name)) return prev.filter((g) => g !== name);
      if (prev.length >= MAX_COMPARE) return prev;
      return [...prev, name];
    });
  }

  const personColors = ["var(--person-1)", "var(--person-2)", "var(--person-3)"];

  return (
    <div className={`app ${isComparing ? "app-wide" : ""}`}>
      <header className="app-header">
        <h1>Genetic Variant Explorer</h1>
        <p className="app-subtitle">
          Disease-associated variant lookup from imputed genome data
        </p>
      </header>

      <div className="controls">
        <div className="control-group">
          <label htmlFor="disease-select">Disease / Trait</label>
          <select
            id="disease-select"
            value={selectedDisease}
            onChange={(e) => setSelectedDisease(e.target.value)}
          >
            <option value="">Select a disease...</option>
            {diseases.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.variant_count} variants)
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label>
            Genomes
            <span className="genome-hint"> (select up to {MAX_COMPARE})</span>
          </label>
          <div className="genome-checkboxes">
            {genomes.map((g, i) => {
              const checked = selectedGenomes.includes(g.name);
              const disabled = !checked && selectedGenomes.length >= MAX_COMPARE;
              const colorIndex = checked ? selectedGenomes.indexOf(g.name) : -1;
              return (
                <label
                  key={g.name}
                  className={`genome-checkbox ${checked ? "checked" : ""} ${disabled ? "disabled" : ""}`}
                  style={checked ? { borderColor: personColors[colorIndex] } : undefined}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    disabled={disabled}
                    onChange={() => toggleGenome(g.name)}
                  />
                  <span
                    className="genome-name"
                    style={checked ? { color: personColors[colorIndex] } : undefined}
                  >
                    {g.name}
                  </span>
                  <span className="genome-chroms">{g.chromosomes.length} chr</span>
                  {g.data_sources && g.data_sources.length > 0 && (
                    <span className="genome-sources">
                      {g.data_sources.map((s) => (
                        <span key={s} className={`genome-source-tag tag-${s}`}>{s}</span>
                      ))}
                    </span>
                  )}
                </label>
              );
            })}
          </div>
        </div>
      </div>

      {selectedDiseaseInfo && reports.length === 0 && !loading && (
        <div className="disease-info">
          <p>{selectedDiseaseInfo.description}</p>
        </div>
      )}

      {loading && <div className="loading">Querying genome data...</div>}
      {error && <div className="error">{error}</div>}

      {merged.length > 0 && (
        <div className="report">
          <div className="report-header">
            <h2>
              {reports[0].disease_name}:{" "}
              {reports.map((r, i) => (
                <span key={r.person}>
                  {i > 0 && ", "}
                  <span className="person-name" style={{ color: personColors[i] }}>
                    {r.person}
                  </span>
                </span>
              ))}
            </h2>
          </div>

          {merged.map((cat) => (
            <CategorySection key={cat.name} cat={cat} isComparing={isComparing} />
          ))}
        </div>
      )}

      <footer className="app-footer">
        <p>
          This tool shows individual genetic variants from published research.
          It does not calculate disease risk. Genetic risk is influenced by
          thousands of variants, lifestyle, and environment. Coordinates:
          GRCh38/hg38. Data source: imputed 23andMe genotype files.
        </p>
      </footer>
    </div>
  );
}
