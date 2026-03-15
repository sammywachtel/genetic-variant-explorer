"""
Multi-SNP interpreters.

Some genes need results from multiple SNPs combined to produce a meaningful
call. APOE is the classic: you need rs429358 + rs7412 to determine the
E2/E3/E4 haplotype.

Interpreters are registered by name and referenced from the disease YAML
files. Add new ones here as needed.
"""

from __future__ import annotations

from typing import Callable

from .models import VariantResult

# Type: takes a dict of rsid -> VariantResult, returns an interpretation string or None
InterpreterFn = Callable[[dict[str, VariantResult]], str | None]


def _sort_allele_pair(pair: str) -> str:
    """Normalize 'C/T' and 'T/C' to the same sorted form."""
    parts = pair.split("/")
    return "/".join(sorted(parts))


# ─── APOE ──────────────────────────────────────────────────────────────────────

APOE_GENOTYPE_TABLE = {
    ("T/T", "C/C"): "E3/E3",
    ("C/T", "C/C"): "E3/E4",
    ("T/C", "C/C"): "E3/E4",
    ("T/T", "C/T"): "E2/E3",
    ("T/T", "T/C"): "E2/E3",
    ("C/C", "C/C"): "E4/E4",
    ("T/T", "T/T"): "E2/E2",
    ("C/T", "C/T"): "E2/E4 (phase-dependent)",
    ("C/T", "T/C"): "E2/E4 (phase-dependent)",
    ("T/C", "C/T"): "E2/E4 (phase-dependent)",
    ("T/C", "T/C"): "E2/E4 (phase-dependent)",
}


def apoe_genotype(results: dict[str, VariantResult]) -> str | None:
    """
    Combine rs429358 + rs7412 into an APOE genotype call.
    Returns e.g. "E3/E4" or None if data is missing.
    """
    r1 = results.get("rs429358")
    r2 = results.get("rs7412")
    if not r1 or not r2:
        return None
    if r1.alleles == "no data" or r2.alleles == "no data":
        return None

    key = (r1.alleles, r2.alleles)
    if key in APOE_GENOTYPE_TABLE:
        return APOE_GENOTYPE_TABLE[key]

    # Try sorted form as fallback
    sorted_key = (_sort_allele_pair(r1.alleles), _sort_allele_pair(r2.alleles))
    if sorted_key in APOE_GENOTYPE_TABLE:
        return APOE_GENOTYPE_TABLE[sorted_key]

    return f"Unknown combination: rs429358={r1.alleles}, rs7412={r2.alleles}"


# ─── Registry ──────────────────────────────────────────────────────────────────
# Maps function names (as referenced in YAML) to actual callables.
# To add a new interpreter: define the function above, add it here.

INTERPRETER_REGISTRY: dict[str, InterpreterFn] = {
    "apoe_genotype": apoe_genotype,
}
