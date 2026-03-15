import type { MergedCategory, PersonVariant } from "./types";
import VariantCard from "./VariantCard";
import RegionCard from "./RegionCard";

const PERSON_COLORS = ["var(--person-1)", "var(--person-2)", "var(--person-3)"];

function countStatus(pv: PersonVariant): "risk" | "protective" | "clear" | "no-data" {
  const { vr } = pv;
  if (vr.alleles === "no data") return "no-data";
  if (!vr.effect_allele || !vr.alleles.includes("/")) return "clear";
  const [a1, a2] = vr.alleles.split("/");
  const count = [a1, a2].filter((a) => a === vr.effect_allele).length;
  if (vr.effect_direction === "risk" && count > 0) return "risk";
  if (vr.effect_direction === "protective" && count > 0) return "protective";
  return "clear";
}

function VariantSummary({ cat, isComparing }: { cat: MergedCategory; isComparing: boolean }) {
  if (cat.variants.length === 0) return null;

  // Collect per-person summaries
  const people = cat.variants[0].people.map((p) => p.person);

  return (
    <div className="variant-summaries">
      {people.map((person, pi) => {
        let risk = 0, protective = 0, clear = 0, noData = 0;
        for (const mv of cat.variants) {
          const pv = mv.people[pi];
          if (!pv) continue;
          const s = countStatus(pv);
          if (s === "risk") risk++;
          else if (s === "protective") protective++;
          else if (s === "no-data") noData++;
          else clear++;
        }
        return (
          <div key={person} className="variant-summary">
            {isComparing && (
              <span className="summary-person" style={{ color: PERSON_COLORS[pi] }}>
                {person}:
              </span>
            )}
            {risk > 0 && <span className="summary-dot risk">{risk} risk</span>}
            {protective > 0 && (
              <span className="summary-dot protective">{protective} protective</span>
            )}
            {clear > 0 && <span className="summary-dot clear">{clear} clear</span>}
            {noData > 0 && (
              <span className="summary-dot no-data">{noData} no data</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function CategorySection({ cat, isComparing }: { cat: MergedCategory; isComparing: boolean }) {
  return (
    <section className="category-section">
      <h2 className="category-name">{cat.name}</h2>
      {cat.description && (
        <p className="category-description">{cat.description}</p>
      )}

      {cat.personInterpretations.length > 0 && (() => {
        // Collect all genes that have interpretations across any person
        const allGenes = new Set<string>();
        for (const pi of cat.personInterpretations) {
          for (const gene of Object.keys(pi.interpretations)) {
            allGenes.add(gene);
          }
        }
        if (allGenes.size === 0) return null;

        return Array.from(allGenes).map((gene) => (
          <div key={gene} className="interpretation-banner">
            <span className="interp-gene">{gene}</span>
            <div className="interp-people">
              {cat.personInterpretations.map((pi, i) => {
                const val = pi.interpretations[gene];
                if (!val) return null;
                return (
                  <span key={pi.person} className="interp-person-value">
                    {isComparing && (
                      <span className="interp-person-name" style={{ color: PERSON_COLORS[i] }}>
                        {pi.person}:
                      </span>
                    )}
                    <span className="interp-value">{val}</span>
                  </span>
                );
              })}
            </div>
          </div>
        ));
      })()}

      <VariantSummary cat={cat} isComparing={isComparing} />

      <div className="variant-grid">
        {cat.variants.map((mv) => (
          <VariantCard key={mv.base.rsid} mv={mv} />
        ))}
        {cat.regions.map((mr) => (
          <RegionCard key={`${mr.base.gene}-${mr.base.start}`} mr={mr} />
        ))}
      </div>
    </section>
  );
}
