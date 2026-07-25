# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install with all extras for development
pip install -e ".[dev,test,elasticsearch]"

# Run tests
python -m pytest -vv

# Run a single test
python -m pytest tests/test_engine.py::test_name -vv

# Lint and format (via pre-commit, as configured)
pre-commit run --all-files

# Ruff standalone (only if pre-commit unavailable)
ruff check --fix --unsafe-fixes --preview
ruff format
```

## Architecture

The library provides a layered search system with three search modes: keyword, vector, and semantic.

**Core abstractions** (`_interfaces.py`):
- `KeywordSearchBackend` — ABC with `async keyword_search(queries)`
- `VectorSearchBackend` — ABC with `async vector_search(query, *, top_n, min_score, allowlist)`
- `SemanticSearchBackend` — ABC with `async semantic_search(query, ...)` that receives the other backends and an LLM callable
- `LLMCompletionFn` — Protocol for an async callable `(messages, *, system) -> str`

**`SearchEngine`** (`_engine.py`) — the central orchestrator. Accepts optional backends at construction; raises `RuntimeError` if a method is called for an unconfigured backend. It delegates to backends and accumulates results into a `SearchSession`.

**`SearchSession`** (`_session.py`) — stateful per-query context. Deduplicates hits across calls. The `allowlist` property returns paths from keyword hits by default, used by vector search to narrow scope when keyword results exist. Can be overridden via `set_allowlist()`.

**`ElasticsearchKeywordBackend`** (`_elasticsearch_backend.py`) — the only built-in backend; requires the `elasticsearch` optional dependency. Lazy-imports elasticsearch at instantiation with a clear error on missing dependency.

**Data types** (`_types.py`): `SearchHit(path, score)` and `SemanticResult(path, score, reasoning)` — both frozen dataclasses.

**Extending**: add new backends by subclassing the relevant ABC from `_interfaces.py`. The `SemanticSearchBackend` receives all configured backends at search time, enabling implementations that combine keyword + vector + LLM reranking.

## Optional dependencies

| Extra | Provides |
|-------|----------|
| `elasticsearch` | `ElasticsearchKeywordBackend` (requires `pydantic >= 2.12.5`) |
| `test` | pytest |
| `dev` | pre-commit, ruff, mypy |
| `doc` | sphinx |
