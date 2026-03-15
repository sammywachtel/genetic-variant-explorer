// Mirrors backend/models.py — keep in sync with the API response shapes.

export interface DiseaseSummary {
  id: string;
  name: string;
  description: string;
  category_count: number;
  variant_count: number;
  region_count: number;
}

export interface GenomeSummary {
  name: string;
  chromosomes: string[];
  data_sources: string[];
}

export type ConfidenceStatus = "current" | "revised" | "legacy" | "disproven";

export interface StudyRef {
  id: string;
  title: string;
  authors: string;
  year: number;
  journal: string;
  doi: string;
  url: string;
  finding: string;
}

export interface VariantResult {
  rsid: string;
  chrom: string;
  pos: number;
  ref: string;
  alt: string;
  gene: string;
  effect: string;
  effect_allele: string;
  effect_direction: "risk" | "protective" | "marker" | "";
  mechanism: string;
  layman: string;
  hds: [number, number] | null;
  alleles: string;
  is_carrier: boolean;
  data_source: string;
  confidence_status: ConfidenceStatus;
  confidence_note: string;
  last_reviewed: string;
  studies: StudyRef[];
}

export interface RegionResult {
  gene: string;
  chrom: string;
  start: number;
  end: number;
  effect: string;
  mechanism: string;
  layman: string;
  likely_redacted: boolean;
  variant_count: number;
  variants_found: { pos: number; ref: string; alt: string; hds: number[] }[];
  effect_direction: string;
  confidence_status: ConfidenceStatus;
  confidence_note: string;
  last_reviewed: string;
  studies: StudyRef[];
}

export interface CategoryResult {
  name: string;
  description: string;
  variant_results: VariantResult[];
  region_results: RegionResult[];
  interpretations: Record<string, string>;
}

export interface DiseaseReport {
  person: string;
  disease_id: string;
  disease_name: string;
  categories: CategoryResult[];
}

// Comparison types — used when viewing 1-3 people side by side

export interface PersonVariant {
  person: string;
  vr: VariantResult;
}

export interface PersonRegion {
  person: string;
  rr: RegionResult;
}

export interface MergedVariant {
  base: VariantResult;
  people: PersonVariant[];
}

export interface MergedRegion {
  base: RegionResult;
  people: PersonRegion[];
}

export interface MergedCategory {
  name: string;
  description: string;
  variants: MergedVariant[];
  regions: MergedRegion[];
  personInterpretations: { person: string; interpretations: Record<string, string> }[];
}
