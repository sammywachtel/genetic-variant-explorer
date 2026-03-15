"""
Core query engine: reads genome data and produces results.

Data priority for each variant:
  1. Raw/phased chip data (directly measured, high confidence)
  2. Imputed BCF data (statistically inferred, lower confidence)

Chip data is looked up by rsID. Imputed data is looked up by genomic position.
Region scans always use imputed data (chip data doesn't cover arbitrary regions).
"""

from __future__ import annotations

import os
from pathlib import Path

import pysam

from . import genome_store
from .interpreters import INTERPRETER_REGISTRY
from .models import (
    Category,
    CategoryResult,
    Disease,
    DiseaseReport,
    RegionDef,
    RegionResult,
    VariantDef,
    VariantResult,
)


# ─── Index Management ──────────────────────────────────────────────────────────

class IndexManager:
    """
    Tracks .csi index files we create so we can clean up after ourselves.
    Nobody wants orphaned index files cluttering up the place.
    """

    def __init__(self):
        self._created: set[str] = set()

    def ensure_index(self, path: Path) -> None:
        csi = str(path) + ".csi"
        if not os.path.isfile(csi):
            from pysam import bcftools as pysam_bcftools
            pysam_bcftools.index("-f", str(path))
            self._created.add(csi)

    def cleanup(self) -> None:
        for csi in self._created:
            if os.path.isfile(csi):
                os.remove(csi)
        self._created.clear()


# ─── Low-level Query Functions ─────────────────────────────────────────────────

def hds_to_alleles(ref: str, alt: str, hds_values: tuple[float, ...]) -> tuple[str, bool]:
    """
    Convert haplotype dosages to allele calls.
    Each HDS value is P(ALT) on that haplotype: ~0 = REF, ~1 = ALT.
    Returns (allele_string, is_carrier).
    """
    calls = [alt if h > 0.5 else ref for h in hds_values]
    alleles = "/".join(calls)
    is_carrier = alt in calls
    return alleles, is_carrier


def _variant_meta(v: VariantDef) -> dict:
    """Fields shared between chip and imputed results."""
    return dict(
        rsid=v.rsid, chrom=v.chrom, pos=v.pos, gene=v.gene, effect=v.effect,
        effect_allele=v.effect_allele, effect_direction=v.effect_direction,
        mechanism=v.mechanism, layman=v.layman,
        confidence_status=v.confidence_status, confidence_note=v.confidence_note,
        last_reviewed=v.last_reviewed, studies=v.studies,
    )


def query_snp_from_chip(v: VariantDef, chip_data: dict[str, dict]) -> VariantResult | None:
    """
    Try to get a variant from directly-measured chip data (by rsID).
    Returns None if the rsID isn't on the chip.
    """
    entry = chip_data.get(v.rsid)
    if entry is None:
        return None

    genotype = entry["genotype"]
    source = entry["source"]

    if genotype == "no data" or genotype in ("--", ""):
        return VariantResult(
            **_variant_meta(v), ref=v.ref, alt=v.alt,
            data_source=source,
        )

    alleles = genotype  # already "A/G" format from loader
    is_carrier = v.alt in alleles.split("/") if "/" in alleles else False

    return VariantResult(
        **_variant_meta(v), ref=v.ref, alt=v.alt,
        alleles=alleles, is_carrier=is_carrier,
        data_source=source,
    )


def query_snp_from_bcf(vcf: pysam.VariantFile, v: VariantDef) -> VariantResult:
    """
    Fetch a single position from the imputed BCF and convert to a result.
    pysam.fetch() uses 0-based half-open coords, VCF positions are 1-based.
    """
    meta = _variant_meta(v)

    try:
        records = list(vcf.fetch(v.chrom, v.pos - 1, v.pos))
    except ValueError:
        return VariantResult(**meta, ref=v.ref, alt=v.alt, data_source="imputed")

    if not records:
        return VariantResult(**meta, ref=v.ref, alt=v.alt, data_source="imputed")

    rec = records[0]
    ref = rec.ref
    alt = rec.alts[0] if rec.alts else v.alt

    sample = rec.samples[0] if rec.samples else None
    hds = None
    alleles = "no data"
    is_carrier = False

    if sample is not None and "HDS" in sample:
        hds_values = sample["HDS"]
        if hds_values is not None:
            hds = tuple(hds_values)
            if alt:
                alleles, is_carrier = hds_to_alleles(ref, alt, hds)

    return VariantResult(
        **meta, ref=ref, alt=alt, hds=hds, alleles=alleles,
        is_carrier=is_carrier, data_source="imputed",
    )


def scan_region(vcf: pysam.VariantFile, r: RegionDef) -> RegionResult:
    """
    Scan a genomic region for any non-reference variants.
    Always uses imputed data — chip data doesn't cover arbitrary regions.
    """
    result = RegionResult(
        gene=r.gene, chrom=r.chrom, start=r.start, end=r.end,
        effect=r.effect, mechanism=r.mechanism, layman=r.layman,
        likely_redacted=r.likely_redacted,
        effect_direction=r.effect_direction,
        confidence_status=r.confidence_status, confidence_note=r.confidence_note,
        last_reviewed=r.last_reviewed, studies=r.studies,
    )

    try:
        records = list(vcf.fetch(r.chrom, r.start - 1, r.end))
    except ValueError:
        return result

    for rec in records:
        sample = rec.samples[0] if rec.samples else None
        if sample is not None and "HDS" in sample:
            hds = tuple(sample["HDS"])
            if any(h > 0.5 for h in hds):
                result.variant_count += 1
                result.variants_found.append({
                    "pos": rec.pos,
                    "ref": rec.ref,
                    "alt": rec.alts[0] if rec.alts else "?",
                    "hds": [round(h, 4) for h in hds],
                })

    return result


# ─── High-level Query ──────────────────────────────────────────────────────────

def query_disease(
    person: str,
    disease: Disease,
    genomes_dir: Path | None = None,
) -> DiseaseReport:
    """
    Run all variant queries for one person against one disease.

    Strategy:
      1. Load chip data (raw/phased) for this person — indexed by rsID
      2. For each variant: try chip data first, fall back to imputed BCF
      3. For regions: always use imputed BCF (chip doesn't cover regions)
    """
    idx = IndexManager()
    report = DiseaseReport(
        person=person,
        disease_id=disease.id,
        disease_name=disease.disease,
    )

    # Step 1: Load chip data (fast — just a dict lookup per variant)
    chip_data = genome_store.load_chip_data(person, genomes_dir)

    # Collect variants that need imputed fallback, grouped by chromosome
    variants_needing_bcf: list[tuple[int, VariantDef]] = []  # (cat_idx, variant)
    # Regions always need BCF
    regions_needing_bcf: list[tuple[int, RegionDef]] = []

    # Pre-create CategoryResult objects
    cat_results: list[CategoryResult] = []
    for category in disease.categories:
        cat_results.append(CategoryResult(
            name=category.name,
            description=category.description,
        ))

    # Step 2: Try chip data for each variant
    for cat_idx, category in enumerate(disease.categories):
        for v in category.variants:
            chip_result = query_snp_from_chip(v, chip_data) if chip_data else None
            if chip_result is not None and chip_result.alleles != "no data":
                cat_results[cat_idx].variant_results.append(chip_result)
            else:
                # Need to try imputed
                variants_needing_bcf.append((cat_idx, v))

        for r in category.regions:
            regions_needing_bcf.append((cat_idx, r))

    # Step 3: Query imputed BCFs for remaining variants and all regions
    chrom_work: dict[str, list[tuple[int, str, VariantDef | RegionDef]]] = {}
    for cat_idx, v in variants_needing_bcf:
        chrom_work.setdefault(v.chrom, []).append((cat_idx, "variant", v))
    for cat_idx, r in regions_needing_bcf:
        chrom_work.setdefault(r.chrom, []).append((cat_idx, "region", r))

    open_files: dict[str, pysam.VariantFile] = {}
    try:
        for chrom, work_items in chrom_work.items():
            path = genome_store.bcf_path(person, chrom, genomes_dir)
            if path is None or not path.is_file():
                for cat_idx, kind, q in work_items:
                    if kind == "variant":
                        v = q
                        cat_results[cat_idx].variant_results.append(VariantResult(
                            **_variant_meta(v), ref=v.ref, alt=v.alt,
                        ))
                    else:
                        r = q
                        cat_results[cat_idx].region_results.append(RegionResult(
                            gene=r.gene, chrom=r.chrom, start=r.start, end=r.end,
                            effect=r.effect, mechanism=r.mechanism, layman=r.layman,
                            likely_redacted=r.likely_redacted,
                            effect_direction=r.effect_direction,
                            confidence_status=r.confidence_status,
                            confidence_note=r.confidence_note,
                            last_reviewed=r.last_reviewed, studies=r.studies,
                        ))
                continue

            idx.ensure_index(path)
            path_str = str(path)
            if path_str not in open_files:
                open_files[path_str] = pysam.VariantFile(path_str)
            vcf = open_files[path_str]

            for cat_idx, kind, q in work_items:
                if kind == "variant":
                    cat_results[cat_idx].variant_results.append(
                        query_snp_from_bcf(vcf, q)
                    )
                else:
                    cat_results[cat_idx].region_results.append(scan_region(vcf, q))

    finally:
        for vcf in open_files.values():
            vcf.close()
        idx.cleanup()

    # Reorder variant_results within each category to match the original
    # definition order (chip results were added first, BCF results after)
    for cat_idx, category in enumerate(disease.categories):
        rsid_order = {v.rsid: i for i, v in enumerate(category.variants)}
        cat_results[cat_idx].variant_results.sort(
            key=lambda vr: rsid_order.get(vr.rsid, 999)
        )

    # Run multi-SNP interpreters
    all_by_rsid: dict[str, VariantResult] = {}
    for cr in cat_results:
        for vr in cr.variant_results:
            all_by_rsid[vr.rsid] = vr

    for cat_idx, category in enumerate(disease.categories):
        for interp_def in category.interpreters:
            fn = INTERPRETER_REGISTRY.get(interp_def.function)
            if fn:
                result = fn(all_by_rsid)
                if result:
                    cat_results[cat_idx].interpretations[interp_def.gene] = result

    report.categories = cat_results
    return report
