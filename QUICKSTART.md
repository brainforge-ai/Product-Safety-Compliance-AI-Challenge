# Quick Start Guide

## Prerequisites

- **Python 3.10+**
- **OpenAI API Key**
- **Poppler** (required for PDF processing):
  - macOS: `brew install poppler`
  - Linux: `apt-get install poppler-utils`

## Setup

```bash
# 1. Create virtual environment and install dependencies
make setup

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Running

### One Command (Setup + Full Eval)

```bash
make dev
```

Runs `make setup`, checks that `.env` exists, then evaluates all sample products under `pdfs/`, `images/`, and `texts/` via the CLI. Use this for a first end-to-end run after adding your API key.

### Web Dashboard

```bash
make ui
# Opens at http://localhost:7860
```

### CLI Batch Evaluation

```bash
# Scan sample directories (pdfs/, images/, texts/)
make eval

# Or use the product index CSV
venv/bin/python scripts/run_eval.py --index product_index.csv
```

### REST API

```bash
make api
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## Project Structure

```
├── src/
│   ├── core/
│   │   ├── extractors/     # PDF/Image/Text extraction (GPT-4o Vision)
│   │   └── matching/       # 3-layer matching pipeline
│   ├── api/                # FastAPI endpoints
│   └── ui/                 # Gradio dashboard
├── scripts/
│   └── run_eval.py         # CLI batch evaluation
├── tests/
├── pdfs/                   # Sample PDF products
├── images/                 # Sample image products
├── texts/                  # Sample text products
├── forbidden_ingredients.csv
├── product_index.csv       # Product file index
└── README.md               # Challenge overview and architecture
```

## Testing

```bash
make test
```

## Commands Reference


| Command      | Description                                             |
| ------------ | ------------------------------------------------------- |
| `make dev`   | Setup venv, then run CLI evaluation on all sample files |
| `make setup` | Create venv and install dependencies                    |
| `make ui`    | Start Gradio dashboard (localhost:7860)                 |
| `make api`   | Start REST API (localhost:8000)                         |
| `make eval`  | Run CLI batch evaluation on sample directories          |
| `make test`  | Run tests                                               |
| `make clean` | Remove venv and cached files                            |


