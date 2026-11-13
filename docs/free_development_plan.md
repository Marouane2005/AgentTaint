# Free Development Plan — Stack Verification

**Status:** Research assessment  
**Date:** 2026-11-13  
**Principle:** Zero mandatory paid APIs. Local-first. CPU-compatible.

---

## Verified free stack

| Component | Choice | License notes | Paid API? |
|-----------|--------|---------------|-----------|
| Language | Python 3.12+ | PSF | No |
| API | FastAPI + Uvicorn | MIT | No |
| Validation | Pydantic v2 | MIT | No |
| ORM | SQLAlchemy 2 + Alembic | MIT | No |
| DB (dev) | SQLite | Public domain | No |
| DB (prod-oriented) | PostgreSQL (self-hosted / Compose) | PostgreSQL License | No |
| MCP | Official `mcp` Python SDK / FastMCP | MIT (verify pin) | No |
| Graph (MVP) | NetworkX | BSD | No |
| Embeddings | Sentence-Transformers + `BAAI/bge-small-en-v1.5` | Apache-2.0 (model card) | No (HF download) |
| ML runtime | PyTorch CPU | BSD-style | No |
| Policy | Deterministic adapter → `cedarpy` | Cedar is open; cedarpy community | No |
| LLM optional | Ollama (local) | MIT | No |
| Frontend | Next.js + TS + Tailwind | MIT | No |
| Charts | Recharts | MIT | No |
| Containers | Docker / Compose | Apache-2.0 | No |
| CI | GitHub Actions | Free for public OSS | No |
| Lint/type | Ruff, MyPy | MIT | No |
| Tests | Pytest, Playwright | MIT / Apache | No |

---

## Hardware requirements (documented targets)

| Profile | CPU | RAM | Disk | Notes |
|---------|-----|-----|------|-------|
| Core tests (no embeddings) | 2 vCPU | 4 GB | 2 GB | CI default |
| Reconstruction enabled | 4 vCPU | 8 GB | 5 GB+ | model ~100–150MB + torch |
| Full demo + dashboard | 4 vCPU | 8–16 GB | 10 GB | Node + Python + Docker shell sandbox |
| Optional Ollama LLM | 8+ GB RAM | + model size | Large | Not required for security engine |

GPU: **not required**.

---

## Dependency risk register

| Risk | Mitigation |
|------|------------|
| PyTorch wheel size / CI time | Optional extra `reconstruction`; mock embeddings in unit tests |
| HuggingFace download on first run | Document; pin revision; optional vendor in Docker layer |
| MCP SDK API churn | Internal ports; pin version in `pyproject.toml` |
| cedarpy platform wheels | Fallback to deterministic adapter (always available) |
| Docker unavailable for shell mock | Skip shell integration tests with clear marker |
| Next.js tooling | Pin Node 20 LTS in docs/Compose |

---

## What we will never require for MVP

- OpenAI / Anthropic / Voyage / paid embedding APIs
- Hosted Neo4j Aura or similar
- Cloud-only vector DBs
- Mandatory GPU
- Real Gmail / production shell access for benchmarks

---

## Reproducibility checklist

- [ ] Pin versions in `pyproject.toml` / lockfile
- [ ] `.env.example` with no secrets required
- [ ] `docker-compose.yml` for API + Postgres + mocks + dashboard
- [ ] `Makefile` targets: `test`, `lint`, `bench-smoke`, `up`
- [ ] Model name + revision pinned in config
- [ ] Benchmark seeds fixed; train/test split documented
- [ ] Research log entries for failed experiments

---

## Licensing posture

Prefer MIT / Apache-2.0 / BSD / PSF.  
Review model card for `bge-small-en-v1.5` before distribution of weights inside images.  
Project license: Apache-2.0 recommended for research + industry reuse (finalize in Week 1).
