"""
Loads the variant database from YAML files.

Each YAML file in variants_db/ defines one disease/trait.
This module knows nothing about genomes or people — pure research catalog.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import Category, Disease, InterpreterDef, RegionDef, StudyRef, VariantDef

DB_DIR = Path(__file__).resolve().parent.parent / "variants_db"


def _load_study(d: dict) -> StudyRef:
    return StudyRef(
        id=d.get("id", ""),
        title=d.get("title", ""),
        authors=d.get("authors", ""),
        year=d.get("year", 0),
        journal=d.get("journal", ""),
        doi=d.get("doi", ""),
        url=d.get("url", ""),
        finding=d.get("finding", ""),
    )


def _load_variant(d: dict) -> VariantDef:
    return VariantDef(
        rsid=d["rsid"],
        chrom=d["chrom"],
        pos=d["pos"],
        ref=d["ref"],
        alt=d["alt"],
        gene=d["gene"],
        effect=d["effect"],
        effect_allele=d.get("effect_allele", ""),
        effect_direction=d.get("effect_direction", ""),
        mechanism=d.get("mechanism", ""),
        layman=d.get("layman", ""),
        source=d.get("source", ""),
        confidence_status=d.get("confidence_status", "current"),
        confidence_note=d.get("confidence_note", ""),
        last_reviewed=d.get("last_reviewed", ""),
        studies=[_load_study(s) for s in d.get("studies", [])],
    )


def _load_region(d: dict) -> RegionDef:
    return RegionDef(
        gene=d["gene"],
        chrom=d["chrom"],
        start=d["start"],
        end=d["end"],
        effect=d["effect"],
        mechanism=d.get("mechanism", ""),
        layman=d.get("layman", ""),
        likely_redacted=d.get("likely_redacted", False),
        effect_direction=d.get("effect_direction", ""),
        confidence_status=d.get("confidence_status", "current"),
        confidence_note=d.get("confidence_note", ""),
        last_reviewed=d.get("last_reviewed", ""),
        studies=[_load_study(s) for s in d.get("studies", [])],
    )


def _load_interpreter(d: dict) -> InterpreterDef:
    return InterpreterDef(
        gene=d["gene"],
        function=d["function"],
        description=d.get("description", ""),
    )


def _load_category(d: dict) -> Category:
    return Category(
        name=d["name"],
        description=d.get("description", "").strip(),
        variants=[_load_variant(v) for v in d.get("variants", [])],
        regions=[_load_region(r) for r in d.get("regions", [])],
        interpreters=[_load_interpreter(i) for i in d.get("interpreters", [])],
    )


def load_disease(path: Path) -> Disease:
    """Load a single disease YAML file."""
    raw = yaml.safe_load(path.read_text())
    return Disease(
        id=path.stem,
        disease=raw["disease"],
        description=raw.get("description", "").strip(),
        categories=[_load_category(c) for c in raw.get("categories", [])],
    )


def load_all_diseases(db_dir: Path | None = None) -> dict[str, Disease]:
    """
    Load every .yaml file in the database directory.
    Returns {disease_id: Disease} where disease_id is the filename stem.
    Skips files starting with underscore (conventions, schemas, etc.).
    """
    db_dir = db_dir or DB_DIR
    diseases = {}
    for path in sorted(db_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        disease = load_disease(path)
        diseases[disease.id] = disease
    return diseases
