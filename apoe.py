#!/usr/bin/env python3
"""
APOE genotype extraction from imputed BCF/VCF files.

Reads a chr19 variant file, extracts the two SNPs that define APOE status
(rs429358 and rs7412), interprets the genotype, and creates an IGV-friendly
VCF.GZ output. Skips extraction if output already exists.

Coordinates assume GRCh38 / hg38.
"""

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pysam

# The two SNPs that define APOE. That's it. Two lousy positions
# determine whether you worry about Alzheimer's at dinner parties.
APOE_SNPS = {
    "rs429358": {"chrom": "chr19", "pos": 44908684},  # 1-based VCF coordinate
    "rs7412":   {"chrom": "chr19", "pos": 44908822},
}

# Haplotype definitions (what allele at each SNP defines each epsilon):
#   E2 = rs429358:T + rs7412:T
#   E3 = rs429358:T + rs7412:C
#   E4 = rs429358:C + rs7412:C
#
# The lookup: (sorted rs429358 alleles, sorted rs7412 alleles) -> result
GENOTYPE_TABLE = {
    ("T/T", "C/C"): ("E3/E3", "rs429358 is T/T and rs7412 is C/C, which corresponds to E3/E3."),
    ("C/T", "C/C"): ("E3/E4", "rs429358 is het (C/T) and rs7412 is C/C, which corresponds to E3/E4."),
    ("T/T", "C/T"): ("E2/E3", "rs429358 is T/T and rs7412 is het (C/T), which corresponds to E2/E3."),
    ("C/C", "C/C"): ("E4/E4", "rs429358 is C/C and rs7412 is C/C, which corresponds to E4/E4."),
    ("T/T", "T/T"): ("E2/E2", "rs429358 is T/T and rs7412 is T/T, which corresponds to E2/E2."),
    ("C/T", "C/T"): (
        "likely E2/E4, but phase matters",
        "Both sites are heterozygous. That pattern is commonly interpreted as E2/E4, but phasing matters for certainty.",
    ),
}


@dataclass
class SNPResult:
    """What we pulled out of the file for one SNP position."""
    rsid: str
    chrom: str
    pos: int
    ref: str
    alt: str
    gt: str        # e.g. "0/1" or "NA"
    alleles: str   # e.g. "C/T" or "NA" — the actual bases
    hds: str       # e.g. "0.98,0.02" or "NA"


def sort_allele_pair(pair: str) -> str:
    """Normalize 'C/T' and 'T/C' to the same sorted form."""
    parts = pair.split("/")
    return "/".join(sorted(parts))


def hds_to_alleles(ref: str, alt: str, hds_values: tuple[float, ...]) -> str:
    """
    Convert haplotype dosages to allele calls.
    Each HDS value is the probability of ALT on that haplotype.
    ~0 = REF, ~1 = ALT. We round at 0.5.
    """
    calls = [alt if h > 0.5 else ref for h in hds_values]
    return "/".join(calls)


def extract_snp(vcf: pysam.VariantFile, rsid: str, chrom: str, pos: int) -> SNPResult | None:
    """
    Fetch a single SNP from the variant file.

    pysam uses 0-based half-open coordinates internally, but fetch()
    accepts 0-based start inclusive, end exclusive. VCF pos 44908684
    becomes fetch(chrom, 44908683, 44908684).
    """
    records = list(vcf.fetch(chrom, pos - 1, pos))
    if not records:
        return None

    rec = records[0]
    ref = rec.ref
    alt = rec.alts[0] if rec.alts else ""

    # Grab the first (usually only) sample
    sample = rec.samples[0] if rec.samples else None
    gt_str = "NA"
    alleles_str = "NA"
    hds_str = "NA"

    if sample is not None:
        # Try GT first
        if "GT" in sample:
            gt_tuple = sample["GT"]
            if gt_tuple is not None:
                sep = "|" if sample.phased else "/"
                gt_str = sep.join(str(a) for a in gt_tuple)
                # Convert numeric GT to actual bases
                allele_map = [ref] + list(rec.alts or [])
                alleles_str = sep.join(allele_map[a] for a in gt_tuple if a is not None)

        # Try HDS — the bread and butter of imputed data
        if "HDS" in sample:
            hds_values = sample["HDS"]
            if hds_values is not None:
                hds_tuple = tuple(hds_values)
                hds_str = ",".join(f"{v:.4g}" for v in hds_tuple)
                # If we didn't get alleles from GT, derive them from HDS
                if alleles_str == "NA" and alt:
                    alleles_str = hds_to_alleles(ref, alt, hds_tuple)

    return SNPResult(
        rsid=rsid, chrom=chrom, pos=pos,
        ref=ref, alt=alt, gt=gt_str,
        alleles=alleles_str, hds=hds_str,
    )


def interpret(snp1: SNPResult, snp2: SNPResult) -> tuple[str, str]:
    """
    Given the two APOE SNP results, figure out the genotype.
    Returns (interpretation, details).
    """
    if snp1.alleles == "NA" or snp2.alleles == "NA":
        return (
            "Unable to determine APOE genotype from available fields.",
            "The file did not provide enough genotype information for a clean call.",
        )

    s1 = sort_allele_pair(snp1.alleles)
    s2 = sort_allele_pair(snp2.alleles)

    if (s1, s2) in GENOTYPE_TABLE:
        result, details = GENOTYPE_TABLE[(s1, s2)]
        return (f"APOE result: {result}", details)

    return (
        "Unable to determine APOE genotype from available fields.",
        f"Got rs429358={s1} and rs7412={s2}, which doesn't match any known APOE combination.",
    )


def format_snp_line(snp: SNPResult) -> str:
    return (
        f"  {snp.rsid:10s}  {snp.chrom}:{snp.pos}  "
        f"REF={snp.ref} ALT={snp.alt} GT={snp.gt} "
        f"alleles={snp.alleles} HDS={snp.hds}"
    )


def create_igv_vcf(input_path: str, output_path: str) -> None:
    """Convert input to bgzipped VCF with tabix index for IGV."""
    with pysam.VariantFile(input_path) as vcf_in:
        with pysam.VariantFile(output_path, "wz", header=vcf_in.header) as vcf_out:
            for rec in vcf_in:
                vcf_out.write(rec)
    pysam.tabix_index(output_path, preset="vcf", force=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract APOE genotype from a chr19 BCF/VCF file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Haplotype definitions (GRCh38):
  E2 = rs429358:T + rs7412:T
  E3 = rs429358:T + rs7412:C
  E4 = rs429358:C + rs7412:C

Common genotype combinations:
  rs429358 T/T  +  rs7412 C/C  =>  E3/E3
  rs429358 C/T  +  rs7412 C/C  =>  E3/E4
  rs429358 T/T  +  rs7412 C/T  =>  E2/E3
  rs429358 C/C  +  rs7412 C/C  =>  E4/E4
  rs429358 T/T  +  rs7412 T/T  =>  E2/E2
  rs429358 C/T  +  rs7412 C/T  =>  E2/E4 (phase matters)

Requirements: pysam (pip install pysam)""",
    )
    parser.add_argument("input", help="chr19 variant file (BCF, VCF, or VCF.GZ)")
    parser.add_argument("output_dir", nargs="?", default=None,
                        help="output directory (defaults to input file's directory)")
    args = parser.parse_args()

    input_path = args.input
    if not os.path.isfile(input_path):
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    out_dir = args.output_dir or str(Path(input_path).resolve().parent)
    out_vcf = os.path.join(out_dir, "apoe_extraction.vcf.gz")
    results_file = os.path.join(out_dir, "apoe_results.txt")

    # Skip if already done
    if (os.path.isfile(out_vcf)
            and os.path.isfile(out_vcf + ".tbi")
            and os.path.isfile(results_file)):
        print("Already done. Saved results:\n")
        print(Path(results_file).read_text())
        return 0

    print("=== APOE extraction and interpretation ===")
    print(f"Input: {input_path}")
    print(f"Output: {out_vcf}\n")

    # pysam needs an index for region queries. If one doesn't exist,
    # we create it and clean up after ourselves.
    input_csi = input_path + ".csi"
    created_index = not os.path.isfile(input_csi)

    print("[1/4] Indexing input (if needed)...")
    if not shutil.which("bcftools"):
        print("ERROR: bcftools not found (needed for indexing BCF files)", file=sys.stderr)
        return 1
    subprocess.run(["bcftools", "index", "-f", input_path], check=True,
                   capture_output=True)
    print("Index ready.\n")

    print("[2/4] Querying APOE positions...")
    vcf = pysam.VariantFile(input_path)
    snps: dict[str, SNPResult | None] = {}
    for rsid, info in APOE_SNPS.items():
        snps[rsid] = extract_snp(vcf, rsid, info["chrom"], info["pos"])
    vcf.close()

    snp1 = snps["rs429358"]
    snp2 = snps["rs7412"]

    if snp1 is None or snp2 is None:
        missing = [rs for rs, s in snps.items() if s is None]
        print(f"ERROR: No records found for: {', '.join(missing)}", file=sys.stderr)
        print("Possible reasons:", file=sys.stderr)
        print("  - wrong genome build", file=sys.stderr)
        print("  - chromosome naming mismatch (chr19 vs 19)", file=sys.stderr)
        print("  - file does not contain these sites", file=sys.stderr)
        return 1

    print("Position summaries:")
    print(format_snp_line(snp1))
    print(format_snp_line(snp2))
    print()

    print("[3/4] Interpreting results...")
    interpretation, details = interpret(snp1, snp2)
    print(interpretation)
    print(details)
    print()

    # Save results for future runs
    results_text = f"""{interpretation}
{details}

Position data:
{format_snp_line(snp1)}
{format_snp_line(snp2)}
"""
    Path(results_file).write_text(results_text)

    print("[4/4] Creating IGV-compatible VCF.GZ...")
    create_igv_vcf(input_path, out_vcf)
    print(f"Created:\n  {out_vcf}\n  {out_vcf}.tbi\n")

    # Clean up the index if we created it
    if created_index and os.path.isfile(input_csi):
        os.remove(input_csi)

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
