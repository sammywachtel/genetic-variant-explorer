"""
Auto-discovers genome directories and loads genotype data.

Directory structure per person:
    genomes/{person}/
        raw/        Directly measured 23andMe chip data (~550K SNPs, rsID-indexed)
        phased/     Phased chip data (allele1/allele2 separated by chromosome)
        imputed/    Statistically inferred BCF files (~30-40M positions)
        zips/       Original zip archives

Data priority: raw > phased > imputed
  - Raw/phased = directly measured on the genotyping chip = high confidence
  - Imputed = statistically guessed from nearby markers = lower confidence
  - For any given rsID, we use the best available source
"""

from __future__ import annotations

import re
from pathlib import Path

GENOMES_DIR = Path(__file__).resolve().parent.parent / "genomes"

BCF_PATTERN = re.compile(r"^(chr[\dXY]+)")


# ─── Discovery ────────────────────────────────────────────────────────────────

def discover_people(genomes_dir: Path | None = None) -> list[str]:
    """
    Return sorted list of person names that have any genome data.
    A directory counts as a person if it has raw/, phased/, or imputed/ data.
    """
    genomes_dir = genomes_dir or GENOMES_DIR
    if not genomes_dir.is_dir():
        return []
    people = []
    for d in sorted(genomes_dir.iterdir()):
        if not d.is_dir():
            continue
        has_raw = any((d / "raw").glob("*.txt")) if (d / "raw").is_dir() else False
        has_phased = any((d / "phased").glob("*.txt")) if (d / "phased").is_dir() else False
        has_imputed = any((d / "imputed").glob("*.bcf")) if (d / "imputed").is_dir() else False
        if has_raw or has_phased or has_imputed:
            people.append(d.name)
    return people


def list_chromosomes(person: str, genomes_dir: Path | None = None) -> list[str]:
    """List all chromosomes available in imputed data for a person."""
    genomes_dir = genomes_dir or GENOMES_DIR
    imputed_dir = genomes_dir / person / "imputed"
    if not imputed_dir.is_dir():
        return []
    chroms = set()
    for bcf in imputed_dir.glob("*.bcf"):
        m = BCF_PATTERN.match(bcf.stem)
        if m:
            chroms.add(m.group(1))
    return sorted(chroms, key=_chrom_sort_key)


def list_data_sources(person: str, genomes_dir: Path | None = None) -> list[str]:
    """List which data sources are available for a person."""
    genomes_dir = genomes_dir or GENOMES_DIR
    person_dir = genomes_dir / person
    sources = []
    if (person_dir / "raw").is_dir() and any((person_dir / "raw").glob("*.txt")):
        sources.append("raw")
    if (person_dir / "phased").is_dir() and any((person_dir / "phased").glob("*.txt")):
        sources.append("phased")
    if (person_dir / "imputed").is_dir() and any((person_dir / "imputed").glob("*.bcf")):
        sources.append("imputed")
    return sources


# ─── Raw/Phased 23andMe Data ──────────────────────────────────────────────────

def _ranked_chip_files(person: str, genomes_dir: Path | None = None) -> list[tuple[Path, str]]:
    """
    Return all chip files for a person, ordered by quality.
    Each entry is (path, source_label).

    Priority:
      1. raw genome — unmodified chip readout, full SNP set
      2. phased_with_parents — best phasing, but may drop some SNPs
      3. phased_genome (main) — standard phased file
      4. other phased files (not statistical/one_parent)

    We load them all so higher-priority files establish each rsID's value,
    and lower-priority files backfill any SNPs the better file missed.
    """
    genomes_dir = genomes_dir or GENOMES_DIR
    person_dir = genomes_dir / person
    files: list[tuple[Path, str]] = []

    # Raw first
    raw_dir = person_dir / "raw"
    if raw_dir.is_dir():
        for f in sorted(raw_dir.glob("genome_*.txt")):
            files.append((f, "raw"))

    # Then phased, in quality order
    phased_dir = person_dir / "phased"
    if phased_dir.is_dir():
        for pattern in ["phased_with_parents_*", "phased_genome_[A-Z]*"]:
            for f in sorted(phased_dir.glob(pattern)):
                files.append((f, "phased"))
        # Any remaining non-statistical, non-one_parent phased files
        seen = {p for p, _ in files}
        for f in sorted(phased_dir.glob("*.txt")):
            if f not in seen and "statistical" not in f.name and "one_parent" not in f.name:
                files.append((f, "phased"))

    return files


def _parse_chip_file(chip_file: Path, source: str) -> dict[str, dict]:
    """Parse a single 23andMe chip file into an rsID-indexed dict."""
    is_phased = "phased" in chip_file.parent.name
    data: dict[str, dict] = {}

    with open(chip_file) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            rsid = parts[0]
            if not rsid.startswith("rs"):
                continue

            chrom = parts[1]
            pos = int(parts[2])

            if is_phased:
                # phased: rsid chrom pos allele1 allele2
                a1, a2 = parts[3], parts[4]
                genotype = f"{a1}/{a2}"
            else:
                # raw: rsid chrom pos genotype
                gt = parts[3]
                if len(gt) == 2:
                    genotype = f"{gt[0]}/{gt[1]}"
                elif gt == "--" or gt == "":
                    genotype = "no data"
                else:
                    genotype = gt

            data[rsid] = {
                "chrom": chrom,
                "pos": pos,
                "genotype": genotype,
                "source": source,
            }

    return data


def load_chip_data(person: str, genomes_dir: Path | None = None) -> dict[str, dict]:
    """
    Load directly-measured chip data into an rsID-indexed dict.

    Returns {rsid: {"chrom": str, "pos": int, "genotype": str, "source": str}}

    Merges all available chip files in priority order: raw > phased_with_parents
    > phased_genome > others. Higher-priority files win for any given rsID,
    lower-priority files backfill SNPs the better file missed.
    (phased_with_parents drops some SNPs during the phasing process —
    without merging, those SNPs would unnecessarily fall back to imputed.)
    """
    ranked = _ranked_chip_files(person, genomes_dir)
    if not ranked:
        return {}

    # Start with the best file, then backfill from the rest
    merged: dict[str, dict] = {}
    for chip_file, source in ranked:
        file_data = _parse_chip_file(chip_file, source)
        for rsid, entry in file_data.items():
            if rsid not in merged:
                merged[rsid] = entry

    return merged


# ─── Imputed BCF Paths ────────────────────────────────────────────────────────

def bcf_path(person: str, chrom: str, genomes_dir: Path | None = None) -> Path | None:
    """
    Find the imputed BCF file for a person + chromosome.
    Now looks in the imputed/ subdirectory.
    """
    genomes_dir = genomes_dir or GENOMES_DIR
    imputed_dir = genomes_dir / person / "imputed"
    if not imputed_dir.is_dir():
        return None

    candidates: list[Path] = []
    for bcf in imputed_dir.glob("*.bcf"):
        m = BCF_PATTERN.match(bcf.stem)
        if m and m.group(1) == chrom:
            candidates.append(bcf)

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Prefer the non-standard name (e.g. chr19_fixed.bcf over chr19.bcf)
    standard = imputed_dir / f"{chrom}.bcf"
    non_standard = [c for c in candidates if c != standard]
    if non_standard:
        return non_standard[0]
    return candidates[0]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _chrom_sort_key(chrom: str) -> tuple[int, str]:
    """Sort chr1..chr22, chrX, chrY naturally."""
    num = chrom.replace("chr", "")
    try:
        return (0, int(num))
    except ValueError:
        return (1, num)
