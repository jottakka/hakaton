# Local Development Setup

## Prerequisites

- [uv](https://docs.astral.sh/uv/) ≥ 0.5 — Python package manager
- Python 3.11+
- pre-commit

## 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Clone and enter the repo

```bash
git clone <repo-url> hakaton
cd hakaton
```

## 3. Install pre-commit hooks

```bash
pip install pre-commit   # or: brew install pre-commit
pre-commit install
```

All hooks run automatically on `git commit`. To run them manually:

```bash
pre-commit run --all-files
```

## 4. Create your local `.env`

```bash
cp .env.example .env
# Edit .env and fill in your secrets — never commit .env
```

Required values for local control-plane work:

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | Personal access token with `repo` + `workflow` scopes |
| `GITHUB_OWNER` | GitHub org or username that owns the benchmarks repo |
| `GITHUB_REPO` | Repository name |

See `.env.example` for the full list.

## 5. Package-specific commands

### aioa

```bash
cd aioa
uv sync --group dev          # install deps
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pytest -q             # test
uv run pytest --cov=src -q   # test + coverage
```

### geo_audit_arcade

```bash
cd tools/geo_audit_arcade
uv sync --extra dev
uv run ruff check .
uv run pytest -q
```

### benchmark_control_arcade

```bash
cd tools/benchmark_control_arcade
uv sync --group dev
uv run ruff check .
uv run pytest -q
```

## 6. Running the BenchmarkControl MCP server locally

```bash
cd tools/benchmark_control_arcade
uv run python -m benchmark_control_arcade.server stdio
```

Requires a valid `.env` at the repo root (or exported environment variables).
