"""
Data models for the variant lookup system.

These are plain dataclasses, not Pydantic — keeps the dependency list short.
The API layer (app.py) handles serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─── Study Reference (shared by variants and regions) ─────────────────────────

@dataclass
class StudyRef:
    """A single study/paper linked to a variant or region."""
    id: str                      # short key, e.g. "lambert_2013"
    title: str = ""
    authors: str = ""            # "Lambert et al."
    year: int = 0
    journal: str = ""
    doi: str = ""                # e.g. "10.1038/ng.2802"
    url: str = ""                # full URL (PubMed, DOI link, etc.)
    finding: str = ""            # what this study found re: this variant


# ─── Database Models (loaded from YAML, pure research data) ────────────────────

@dataclass
class VariantDef:
    """A single SNP from the research database. No personal data here."""
    rsid: str
    chrom: str
    pos: int            # 1-based GRCh38
    ref: str
    alt: str
    gene: str
    effect: str
    effect_allele: str = ""
    effect_direction: str = ""   # "risk", "protective", or "marker"
    mechanism: str = ""          # biological mechanism (what happens in the body)
    layman: str = ""             # plain-English interpretation for non-scientists
    source: str = ""
    # ─── New: study metadata and confidence tracking ─────────────
    confidence_status: str = "current"   # "current", "revised", "legacy", "disproven"
    confidence_note: str = ""            # why this status was assigned
    last_reviewed: str = ""              # ISO date of last literature review
    studies: list[StudyRef] = field(default_factory=list)


@dataclass
class RegionDef:
    """A gene region from the research database."""
    gene: str
    chrom: str
    start: int          # 1-based inclusive
    end: int            # 1-based inclusive
    effect: str
    mechanism: str = ""
    layman: str = ""
    likely_redacted: bool = False
    effect_direction: str = ""
    # ─── New: study metadata and confidence tracking ─────────────
    confidence_status: str = "current"
    confidence_note: str = ""
    last_reviewed: str = ""
    studies: list[StudyRef] = field(default_factory=list)


@dataclass
class InterpreterDef:
    """Reference to a multi-SNP interpreter function."""
    gene: str
    function: str       # name in the interpreter registry
    description: str = ""


@dataclass
class Category:
    """A group of related variants within a disease."""
    name: str
    description: str = ""
    variants: list[VariantDef] = field(default_factory=list)
    regions: list[RegionDef] = field(default_factory=list)
    interpreters: list[InterpreterDef] = field(default_factory=list)


@dataclass
class Disease:
    """A disease/trait with its full variant catalog. Pure research."""
    id: str             # filename stem, e.g. "alzheimers"
    disease: str        # display name
    description: str
    categories: list[Category] = field(default_factory=list)


# ─── Result Models (produced by querying a genome) ─────────────────────────────

@dataclass
class VariantResult:
    """What we got back from a BCF file for one variant."""
    rsid: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gene: str
    effect: str
    effect_allele: str = ""
    effect_direction: str = ""
    mechanism: str = ""
    layman: str = ""
    hds: tuple[float, float] | None = None
    alleles: str = "no data"
    is_carrier: bool = False
    data_source: str = ""       # "raw", "phased", or "imputed"
    # ─── New: study metadata and confidence tracking ─────────────
    confidence_status: str = "current"
    confidence_note: str = ""
    last_reviewed: str = ""
    studies: list[StudyRef] = field(default_factory=list)


@dataclass
class RegionResult:
    """What we got back for a region scan."""
    gene: str
    chrom: str
    start: int
    end: int
    effect: str
    mechanism: str = ""
    layman: str = ""
    likely_redacted: bool = False
    variant_count: int = 0
    variants_found: list[dict] = field(default_factory=list)
    effect_direction: str = ""
    # ─── New: study metadata and confidence tracking ─────────────
    confidence_status: str = "current"
    confidence_note: str = ""
    last_reviewed: str = ""
    studies: list[StudyRef] = field(default_factory=list)


@dataclass
class CategoryResult:
    """Results for one category, with optional interpreter output."""
    name: str
    description: str
    variant_results: list[VariantResult] = field(default_factory=list)
    region_results: list[RegionResult] = field(default_factory=list)
    interpretations: dict[str, str] = field(default_factory=dict)
    # e.g. {"APOE": "E3/E4"}


@dataclass
class DiseaseReport:
    """Complete results for one person + one disease."""
    person: str
    disease_id: str
    disease_name: str
    categories: list[CategoryResult] = field(default_factory=list)
