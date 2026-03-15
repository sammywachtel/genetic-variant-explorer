import { useState } from "react";
import type { VariantResult, MergedVariant, StudyRef, ConfidenceStatus } from "./types";

const PERSON_COLORS = ["var(--person-1)", "var(--person-2)", "var(--person-3)"];

function effectAlleleCount(vr: VariantResult): number | null {
  if (!vr.effect_allele || vr.alleles === "no data" || !vr.alleles.includes("/"))
    return null;
  const [a1, a2] = vr.alleles.split("/");
  return [a1, a2].filter((a) => a === vr.effect_allele).length;
}

function verdict(vr: VariantResult, count: number): string {
  const ea = vr.effect_allele;
  const d = vr.effect_direction;

  if (d === "risk") {
    if (count === 0) return `No ${ea} alleles — not at increased risk`;
    if (count === 1) return `1 copy of ${ea} — carries risk allele`;
    return `2 copies of ${ea} — homozygous for risk allele`;
  }
  if (d === "protective") {
    if (count === 0) return `No ${ea} alleles — does not carry protective variant`;
    if (count === 1) return `1 copy of ${ea} — carries one protective allele`;
    return `2 copies of ${ea} — homozygous for protective allele`;
  }
  return `${count} copies of ${ea}`;
}

function statusClass(vr: VariantResult, count: number | null): string {
  if (vr.alleles === "no data") return "no-data";
  if (count === null) return "neutral";
  const d = vr.effect_direction;
  if (d === "risk") {
    if (count === 0) return "clear";
    if (count === 1) return "risk-het";
    return "risk-hom";
  }
  if (d === "protective") {
    if (count === 0) return "neutral";
    if (count === 1) return "protective-het";
    return "protective-hom";
  }
  return "neutral";
}

// Pick the "most significant" status for the card border when comparing
function worstStatus(people: { vr: VariantResult }[]): string {
  const priority = ["risk-hom", "risk-het", "protective-hom", "protective-het", "clear", "neutral", "no-data"];
  let worst = "no-data";
  for (const { vr } of people) {
    const count = effectAlleleCount(vr);
    const s = statusClass(vr, count);
    if (priority.indexOf(s) < priority.indexOf(worst)) worst = s;
  }
  return worst;
}

const CONFIDENCE_LABELS: Record<ConfidenceStatus, string> = {
  current: "Current",
  revised: "Revised",
  legacy: "Legacy",
  disproven: "Disproven",
};

const CONFIDENCE_DESCRIPTIONS: Record<ConfidenceStatus, string> = {
  current: "This variant's mechanism and effect direction are supported by current research.",
  revised: "The core association holds, but the mechanism or interpretation has been significantly updated by newer studies.",
  legacy: "This variant was identified in earlier studies. Its relevance or mechanism is now questioned by more recent research.",
  disproven: "Current evidence no longer supports this variant's originally reported association or mechanism.",
};

function ConfidenceBadge({ status, note }: { status: ConfidenceStatus; note: string }) {
  if (!status || status === "current") return null;

  return (
    <span
      className={`confidence-badge confidence-${status}`}
      title={note || CONFIDENCE_DESCRIPTIONS[status]}
    >
      <span className="confidence-icon">
        {status === "revised" ? "~" : status === "legacy" ? "!" : "\u2715"}
      </span>
      {CONFIDENCE_LABELS[status]}
    </span>
  );
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

function PersonGenotype({ vr, person, color, showName }: {
  vr: VariantResult;
  person: string;
  color: string;
  showName: boolean;
}) {
  const count = effectAlleleCount(vr);
  const status = statusClass(vr, count);

  return (
    <div className={`person-genotype person-status-${status}`} style={{ borderColor: color }}>
      {showName && (
        <span className="person-label" style={{ color }}>{person}</span>
      )}
      <div className="variant-genotype">
        {vr.alleles === "no data" ? (
          <span className="genotype-value missing">No data</span>
        ) : (
          <>
            <span className="genotype-label">Genotype:</span>
            <span className="genotype-value">{vr.alleles}</span>
            {vr.hds && (
              <span
                className="hds-value"
                title="Haplotype Dosage Score — probability of ALT allele on each chromosome copy. Values near 0.00 = likely REF, near 1.00 = likely ALT. These are statistical estimates from imputation, not direct measurements."
              >
                HDS: {vr.hds[0].toFixed(2)}, {vr.hds[1].toFixed(2)}
              </span>
            )}
            {vr.data_source && (
              <span
                className={`source-badge source-${vr.data_source}`}
                title={
                  vr.data_source === "imputed"
                    ? "This genotype was statistically inferred (imputed), not directly measured. Lower confidence."
                    : vr.data_source === "raw"
                    ? "Directly measured on the 23andMe genotyping chip. High confidence."
                    : "Phased chip data — directly measured, with chromosome assignment. High confidence."
                }
              >
                {vr.data_source === "imputed" ? "imputed" : "chip"}
              </span>
            )}
          </>
        )}
      </div>
      {count !== null && (
        <div className="variant-verdict">{verdict(vr, count)}</div>
      )}
    </div>
  );
}

export default function VariantCard({ mv }: { mv: MergedVariant }) {
  const { base, people } = mv;
  const isComparing = people.length > 1;
  const cardStatus = isComparing ? "neutral" : statusClass(people[0].vr, effectAlleleCount(people[0].vr));
  const confidence = (base.confidence_status || "current") as ConfidenceStatus;

  return (
    <div className={`variant-card ${cardStatus} ${confidence !== "current" ? `card-${confidence}` : ""}`}>
      <div className="variant-header">
        <span className="variant-rsid">{base.rsid}</span>
        <span className="variant-gene">{base.gene}</span>
        <ConfidenceBadge status={confidence} note={base.confidence_note} />
        <span className="variant-pos">
          {base.chrom}:{base.pos.toLocaleString()}
        </span>
      </div>

      {confidence !== "current" && base.confidence_note && (
        <div className={`confidence-note confidence-note-${confidence}`}>
          {base.confidence_note}
        </div>
      )}

      <div className={isComparing ? "comparison-genotypes" : ""}>
        {people.map((pv, i) => (
          <PersonGenotype
            key={pv.person}
            vr={pv.vr}
            person={pv.person}
            color={PERSON_COLORS[i]}
            showName={isComparing}
          />
        ))}
      </div>

      <div className="variant-effect">{base.effect}</div>

      {base.mechanism && (
        <div className="variant-mechanism">{base.mechanism}</div>
      )}

      {base.layman && (
        <div className="variant-layman">{base.layman}</div>
      )}

      <StudiesPanel studies={base.studies} lastReviewed={base.last_reviewed} />
    </div>
  );
}
