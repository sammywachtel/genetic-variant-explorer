import { useState } from "react";
import type { RegionResult, MergedRegion, StudyRef, ConfidenceStatus } from "./types";

const PERSON_COLORS = ["var(--person-1)", "var(--person-2)", "var(--person-3)"];

const CONFIDENCE_LABELS: Record<ConfidenceStatus, string> = {
  current: "Current",
  revised: "Revised",
  legacy: "Legacy",
  disproven: "Disproven",
};

function regionSpanKb(rr: RegionResult): string {
  const kb = Math.round((rr.end - rr.start) / 1000);
  return `${kb.toLocaleString()} kb`;
}

function StudyLink({ study }: { study: StudyRef }) {
  const href = study.doi
    ? `https://doi.org/${study.doi}`
    : study.url || "#";

  return (
    <div className="study-entry">
      <a
        className="study-link"
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        title={study.title}
      >
        {study.authors}{study.year ? ` (${study.year})` : ""}
      </a>
      {study.journal && <span className="study-journal"> {study.journal}</span>}
      {study.finding && <p className="study-finding">{study.finding}</p>}
    </div>
  );
}

function StudiesPanel({ studies, lastReviewed }: { studies: StudyRef[]; lastReviewed: string }) {
  const [open, setOpen] = useState(false);

  if (!studies || studies.length === 0) return null;

  return (
    <div className="studies-panel">
      <button className="studies-toggle" onClick={() => setOpen(!open)}>
        {open ? "\u25BC" : "\u25B6"} Studies ({studies.length})
        {lastReviewed && (
          <span className="last-reviewed">reviewed {lastReviewed}</span>
        )}
      </button>
      {open && (
        <div className="studies-list">
          {studies.map((s, i) => (
            <StudyLink key={s.id || s.doi || `study-${i}`} study={s} />
          ))}
        </div>
      )}
    </div>
  );
}

function RegionStatus({ rr, person, color, showName }: {
  rr: RegionResult;
  person: string;
  color: string;
  showName: boolean;
}) {
  const span = regionSpanKb(rr);

  return (
    <div className="person-genotype" style={{ borderColor: color }}>
      {showName && (
        <span className="person-label" style={{ color }}>{person}</span>
      )}
      {rr.likely_redacted ? (
        rr.variant_count === 0 ? (
          <div className="region-status region-empty">
            Scanned {span} region — no non-reference variants found.
            This region was likely redacted by 23andMe before imputation.
          </div>
        ) : (
          <div className="region-status region-noise">
            Scanned {span} region — {rr.variant_count} position{rr.variant_count > 1 ? "s" : ""} differ
            from the reference genome. This is expected imputation noise, not evidence of a
            disease-causing mutation. A region this size normally has hundreds of common
            variants in any genome.
          </div>
        )
      ) : (
        <div className="region-status">
          Scanned {span} region — {rr.variant_count} non-reference
          variant{rr.variant_count !== 1 ? "s" : ""} found.
        </div>
      )}
    </div>
  );
}

export default function RegionCard({ mr }: { mr: MergedRegion }) {
  const { base, people } = mr;
  const isComparing = people.length > 1;
  const confidence = (base.confidence_status || "current") as ConfidenceStatus;

  return (
    <div className={`variant-card region-card ${confidence !== "current" ? `card-${confidence}` : ""}`}>
      <div className="variant-header">
        <span className="region-badge">Gene Region Scan</span>
        <span className="variant-gene">{base.gene}</span>
        {confidence !== "current" && (
          <span className={`confidence-badge confidence-${confidence}`}>
            <span className="confidence-icon">
              {confidence === "revised" ? "~" : confidence === "legacy" ? "!" : "\u2715"}
            </span>
            {CONFIDENCE_LABELS[confidence]}
          </span>
        )}
        <span className="variant-pos">
          {base.chrom}:{base.start.toLocaleString()}-{base.end.toLocaleString()}
        </span>
      </div>

      {confidence !== "current" && base.confidence_note && (
        <div className={`confidence-note confidence-note-${confidence}`}>
          {base.confidence_note}
        </div>
      )}

      <div className="variant-effect">{base.effect}</div>

      {base.mechanism && (
        <div className="variant-mechanism">{base.mechanism}</div>
      )}

      {base.layman && (
        <div className="variant-layman">{base.layman}</div>
      )}

      <div className={isComparing ? "comparison-genotypes" : ""}>
        {people.map((pr, i) => (
          <RegionStatus
            key={pr.person}
            rr={pr.rr}
            person={pr.person}
            color={PERSON_COLORS[i]}
            showName={isComparing}
          />
        ))}
      </div>

      {base.likely_redacted && (
        <div className="region-warning">
          <strong>Why is this here?</strong> Mutations in {base.gene} are known
          to cause early-onset Alzheimer's, but 23andMe redacts raw data for
          medically actionable genes. The imputation process fills in these
          gaps statistically — it guesses what might be there based on nearby
          markers. The variants shown above are <strong>these guesses</strong>,
          not actual measurements. They cannot tell you whether you carry a
          disease-causing mutation. Only clinical genetic testing (such as
          targeted sequencing) can answer that question.
        </div>
      )}

      <StudiesPanel studies={base.studies || []} lastReviewed={base.last_reviewed || ""} />
    </div>
  );
}
