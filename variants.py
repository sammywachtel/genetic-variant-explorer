#!/usr/bin/env python3
"""
CLI for querying genetic variants from imputed 23andMe BCF files.

Thin wrapper around the backend modules. The real logic lives in backend/.

Usage:
    python3 variants.py sam                                # Full report, all diseases
    python3 variants.py alex --disease alzheimers          # One disease
    python3 variants.py olga --category "APOE"             # Filter by category
    python3 variants.py joseph --gene PICALM CLU           # Filter by gene
    python3 variants.py sam --snp rs429358                 # Single SNP
    python3 variants.py --list                              # Show database
    python3 variants.py --list-genomes                      # Show available genomes
    python3 variants.py sam --json                          # JSON output
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from backend import genome_store
from backend.models import CategoryResult, DiseaseReport, RegionResult, VariantResult
from backend.query_engine import query_disease
from backend.variant_db import load_all_diseases


# ─── Report Formatting ────────────────────────────────────────────────────────

def format_hds(hds: tuple[float, float] | None) -> str:
    if hds is None:
        return "--"
    return f"{hds[0]:.2f}, {hds[1]:.2f}"


def _verdict(vr: VariantResult) -> str | None:
    """
    Plain-English summary: what does this genotype mean?
    Connects the file data (alleles) to the science (effect_allele + direction).
    """
    if not vr.effect_allele or vr.alleles == "no data" or "/" not in vr.alleles:
        return None

    a1, a2 = vr.alleles.split("/")
    count = sum(1 for a in (a1, a2) if a == vr.effect_allele)
    ea = vr.effect_allele
    d = vr.effect_direction

    if d == "risk":
        if count == 0:
            return f"no {ea} alleles (not at increased risk from this variant)"
        elif count == 1:
            return f"1 copy of {ea} (carries risk allele)"
        else:
            return f"2 copies of {ea} (homozygous for risk allele)"
    elif d == "protective":
        if count == 0:
            return f"no {ea} alleles (does not carry protective variant)"
        elif count == 1:
            return f"1 copy of {ea} (carries one protective allele)"
        else:
            return f"2 copies of {ea} (homozygous for protective allele)"
    else:
        return f"{count} copies of {ea}"


def format_variant(vr: VariantResult) -> list[str]:
    """Format one variant result as human-readable lines."""
    lines = []

    if vr.alleles == "no data":
        lines.append(
            f"  {vr.rsid:14s}  {vr.chrom}:{vr.pos:<12d}"
            f"  Genotype: --  (no data at this position)"
        )
    else:
        lines.append(
            f"  {vr.rsid:14s}  {vr.chrom}:{vr.pos:<12d}"
            f"  Genotype: {vr.alleles}  (HDS: {format_hds(vr.hds)})"
        )

    lines.append(f"    {vr.gene}: {vr.effect}")

    verdict = _verdict(vr)
    if verdict:
        lines.append(f"    Result: {verdict}")

    return lines


def format_region(rr: RegionResult) -> list[str]:
    """Format one region result."""
    lines = []
    region_str = f"{rr.chrom}:{rr.start}-{rr.end}"
    if rr.likely_redacted:
        if rr.variant_count == 0:
            lines.append(f"  {rr.gene:14s}  {region_str}  no variants (region may be redacted)")
        else:
            lines.append(
                f"  {rr.gene:14s}  {region_str}  "
                f"{rr.variant_count} imputed variant(s) (low confidence -- not directly measured)"
            )
    else:
        lines.append(
            f"  {rr.gene:14s}  {region_str}  "
            f"{rr.variant_count} non-ref variant(s) found"
        )
    lines.append(f"    {rr.effect}")
    return lines


def format_report(report: DiseaseReport) -> str:
    """Build the full human-readable report from a DiseaseReport."""
    lines = [f"\n=== {report.disease_name}: {report.person.capitalize()} ===\n"]

    for cat in report.categories:
        lines.append(cat.name)

        for vr in cat.variant_results:
            lines.extend(format_variant(vr))
        for rr in cat.region_results:
            lines.extend(format_region(rr))

        for gene, interp in cat.interpretations.items():
            lines.append(f"  >> {gene} Genotype: {interp}")

        lines.append("")

    return "\n".join(lines)


# ─── List Commands ─────────────────────────────────────────────────────────────

def list_database(diseases: dict) -> str:
    """Show all diseases and their variants."""
    lines = ["Variant Database:\n"]
    for did, disease in diseases.items():
        lines.append(f"  {disease.disease} ({did})")
        for cat in disease.categories:
            lines.append(f"    {cat.name}")
            for v in cat.variants:
                lines.append(f"      {v.rsid:14s}  {v.chrom}:{v.pos}  {v.gene}")
            for r in cat.regions:
                tag = " [likely redacted]" if r.likely_redacted else ""
                lines.append(f"      {'(region)':14s}  {r.chrom}:{r.start}-{r.end}  {r.gene}{tag}")
        lines.append("")
    return "\n".join(lines)


def list_genomes() -> str:
    """Show available genomes."""
    people = genome_store.discover_people()
    if not people:
        return f"No genomes found in {genome_store.GENOMES_DIR}"
    lines = ["Available genomes:\n"]
    for p in people:
        chroms = genome_store.list_chromosomes(p)
        lines.append(f"  {p:12s}  {len(chroms)} chromosomes")
    return "\n".join(lines)


# ─── Serialization ─────────────────────────────────────────────────────────────

def report_to_json(report: DiseaseReport) -> str:
    """Serialize a DiseaseReport to JSON."""
    def convert(obj):
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            d = {}
            for f in dataclasses.fields(obj):
                d[f.name] = convert(getattr(obj, f.name))
            return d
        elif isinstance(obj, list):
            return [convert(i) for i in obj]
        elif isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        elif isinstance(obj, tuple):
            return list(obj)
        return obj
    return json.dumps(convert(report), indent=2)


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    diseases = load_all_diseases()
    people = genome_store.discover_people()

    parser = argparse.ArgumentParser(
        description="Look up genetic variants from imputed genome data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Available genomes: {', '.join(people) or '(none found)'}\n"
            f"Available diseases: {', '.join(diseases.keys()) or '(none found)'}\n"
            "Use --list to see the full variant database."
        ),
    )
    parser.add_argument("person", nargs="?", help="Genome to query")
    parser.add_argument("--disease", default=None, help="Disease/trait ID (default: all)")
    parser.add_argument("--category", default=None, help="Filter by category (substring)")
    parser.add_argument("--gene", nargs="+", default=None, help="Filter by gene name(s)")
    parser.add_argument("--snp", nargs="+", default=None, help="Filter by rsID(s)")
    parser.add_argument("--list", action="store_true", help="List the variant database")
    parser.add_argument("--list-genomes", action="store_true", help="List available genomes")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.list:
        print(list_database(diseases))
        return 0

    if args.list_genomes:
        print(list_genomes())
        return 0

    if not args.person:
        parser.print_help()
        return 1

    person = args.person.lower()
    if person not in people:
        print(f"ERROR: Genome '{person}' not found. Available: {', '.join(people)}", file=sys.stderr)
        return 1

    # Which diseases to query
    if args.disease:
        if args.disease not in diseases:
            print(f"ERROR: Disease '{args.disease}' not found. Available: {', '.join(diseases.keys())}", file=sys.stderr)
            return 1
        targets = {args.disease: diseases[args.disease]}
    else:
        targets = diseases

    for did, disease in targets.items():
        # Apply filters by building a filtered disease object
        filtered = _filter_disease(disease, args.category, args.gene, args.snp)
        if not any(c.variants or c.regions for c in filtered.categories):
            continue

        print(f"Querying {disease.disease} for {person.capitalize()}...", file=sys.stderr)
        report = query_disease(person, filtered)

        if args.json:
            print(report_to_json(report))
        else:
            print(format_report(report))

    return 0


def _filter_disease(disease, category_filter, gene_filter, snp_filter):
    """Return a copy of the disease with filters applied to categories."""
    from backend.models import Category, Disease

    if not category_filter and not gene_filter and not snp_filter:
        return disease

    filtered_cats = []
    for cat in disease.categories:
        if category_filter and category_filter.lower() not in cat.name.lower():
            continue

        variants = cat.variants
        regions = cat.regions

        if gene_filter:
            upper = [g.upper() for g in gene_filter]
            variants = [v for v in variants if v.gene.upper() in upper]
            regions = [r for r in regions if r.gene.upper() in upper]

        if snp_filter:
            variants = [v for v in variants if v.rsid in snp_filter]
            regions = []  # regions don't have rsids

        if variants or regions:
            filtered_cats.append(Category(
                name=cat.name, description=cat.description,
                variants=variants, regions=regions,
                interpreters=cat.interpreters,
            ))

    return Disease(
        id=disease.id, disease=disease.disease,
        description=disease.description, categories=filtered_cats,
    )


if __name__ == "__main__":
    sys.exit(main())
