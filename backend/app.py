"""
FastAPI application — serves the variant lookup API.

Start with:
    uvicorn backend.app:app --reload --port 8000

Or:
    python -m backend.app
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import genome_store
from .query_engine import query_disease
from .variant_db import load_all_diseases

app = FastAPI(
    title="Genetic Variant Explorer",
    description="Look up disease-associated genetic variants from imputed genome data.",
    version="0.1.0",
)

# Allow the frontend dev server to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this if you ever deploy beyond localhost
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the research database once at startup
DISEASES = load_all_diseases()


# ─── Helpers ───────────────────────────────────────────────────────────────────

def _dc_to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts for JSON serialization."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        d = {}
        for f in dataclasses.fields(obj):
            val = getattr(obj, f.name)
            d[f.name] = _dc_to_dict(val)
        return d
    elif isinstance(obj, list):
        return [_dc_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _dc_to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, tuple):
        return list(obj)
    return obj


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/diseases")
def list_diseases():
    """List all available diseases/traits in the database."""
    return [
        {
            "id": d.id,
            "name": d.disease,
            "description": d.description,
            "category_count": len(d.categories),
            "variant_count": sum(len(c.variants) for c in d.categories),
            "region_count": sum(len(c.regions) for c in d.categories),
        }
        for d in DISEASES.values()
    ]


@app.get("/api/diseases/{disease_id}")
def get_disease(disease_id: str):
    """Get full variant database for one disease (no personal data)."""
    disease = DISEASES.get(disease_id)
    if not disease:
        raise HTTPException(404, f"Disease '{disease_id}' not found")
    return _dc_to_dict(disease)


@app.get("/api/genomes")
def list_genomes():
    """List available genome directories (auto-discovered)."""
    people = genome_store.discover_people()
    return [
        {
            "name": p,
            "chromosomes": genome_store.list_chromosomes(p),
            "data_sources": genome_store.list_data_sources(p),
        }
        for p in people
    ]


@app.get("/api/query/{person}/{disease_id}")
def query_person_disease(person: str, disease_id: str):
    """
    Run variant queries for one person against one disease.
    This is the main endpoint — the heart of the tool.
    """
    disease = DISEASES.get(disease_id)
    if not disease:
        raise HTTPException(404, f"Disease '{disease_id}' not found")

    people = genome_store.discover_people()
    if person not in people:
        raise HTTPException(404, f"Genome '{person}' not found. Available: {people}")

    report = query_disease(person, disease)
    return _dc_to_dict(report)


# ─── Run directly ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
