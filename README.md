# Genetic Variant Explorer

A local-first tool for querying disease-associated genetic variants from 23andMe data. Includes a Python backend, React frontend, and CLI tools for exploring your genome — no data leaves your machine.

## What it does

- **Variant lookup**: Query known disease-associated SNPs (e.g., Alzheimer's APOE status, hATTR amyloidosis) against your imputed genome data
- **Multi-source data**: Merges raw 23andMe chip data, phased data, and imputed BCF files, prioritizing higher-confidence sources
- **Web UI**: React frontend for browsing results by disease, category, gene, or SNP
- **CLI tools**: Command-line scripts for quick lookups and APOE extraction
- **Variant database**: YAML-based disease definitions with effect alleles, risk directions, and interpretations

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- `bcftools` and `tabix` (for imputed BCF data)

Install Python dependencies:

```bash
pip install pysam pyyaml fastapi uvicorn
```

Install frontend dependencies:

```bash
cd frontend && npm install
```

### Adding your 23andMe data

Your genetic data goes in the `genomes/` directory (which is gitignored — nothing leaves your machine).

#### Directory structure

```
genomes/
├── yourname/
│   ├── raw/          # Raw 23andMe export files
│   ├── phased/       # Phased data (from 23andMe phasing feature)
│   └── imputed/      # Imputed BCF files (from Michigan Imputation Server etc.)
```

#### Step 1: Raw 23andMe data

1. Go to [23andMe](https://you.23andme.com/) → **Settings** → **23andMe Data** → **Download Your Data**
2. Select **Browse Raw Data** and download your raw data file
3. Place it in `genomes/yourname/raw/`:

```bash
mkdir -p genomes/yourname/raw
mv ~/Downloads/genome_YourName_v5_Full_*.txt genomes/yourname/raw/
```

#### Step 2: Phased data (optional)

If you have family members on 23andMe who have opted into DNA Relatives, you may have phased data available:

1. Go to **23andMe** → **Settings** → **23andMe Data** → **Download Your Data**
2. Look for **Phased** data download options
3. Place files in `genomes/yourname/phased/`

#### Step 3: Imputed data (optional, but recommended)

Imputation fills in ~30-40 million variant positions from your ~550K chip measurements. This is how you get coverage of most disease-associated SNPs.

1. Download your raw data from 23andMe (Step 1 above)
2. Upload to the [Michigan Imputation Server](https://imputationserver.sph.umich.edu/) or [TOPMed Imputation Server](https://imputation.biodatacatalyst.nhlbi.nih.gov/)
   - Reference panel: TOPMed r2 or HRC r1.1
   - Build: GRCh38/hg38
3. Download the imputed results (you'll get per-chromosome BCF/VCF files)
4. Place the BCF files in `genomes/yourname/imputed/`:

```bash
mkdir -p genomes/yourname/imputed
# After unzipping the imputation results:
mv chr*.bcf genomes/yourname/imputed/
```

#### Multiple people

Add a separate directory for each person:

```
genomes/
├── alice/
│   ├── raw/
│   └── imputed/
├── bob/
│   └── imputed/
```

### Running

Start both servers with one command:

```bash
./start.sh
```

This will:
- Find available ports (defaults: backend=8000, frontend=5173)
- Start the FastAPI backend
- Start the Vite dev server
- Open at `http://localhost:5173`

### CLI usage

```bash
# Full report for a person, all diseases
python3 variants.py alice

# One disease
python3 variants.py alice --disease alzheimers

# Filter by gene
python3 variants.py alice --gene APOE PICALM

# Single SNP lookup
python3 variants.py alice --snp rs429358

# List the variant database
python3 variants.py --list

# List available genomes
python3 variants.py --list-genomes

# APOE extraction from a BCF file
python3 apoe.py genomes/alice/imputed/chr19.bcf
```

## Adding disease definitions

Disease variants are defined in YAML files under `variants_db/`. See the existing files for the format — each file defines categories of variants with their rsIDs, genomic positions, effect alleles, and clinical interpretations.

## Important notes

- **Privacy**: All processing happens locally. No genetic data is transmitted anywhere.
- **Not medical advice**: This is a research/exploration tool. Consult a genetic counselor for clinical interpretation.
- **Data confidence**: The tool distinguishes between directly-measured (raw/phased) and imputed (statistically inferred) variants. Imputed data is lower confidence, especially for rare variants.
