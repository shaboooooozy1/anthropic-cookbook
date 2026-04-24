# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

A collection of Jupyter notebooks and Python examples for building with the Claude API. The repo is structured as a "cookbook": each notebook stands alone, demonstrates a single concept, and is intentionally checked in **with its outputs** so users see expected results without re-running.

Python 3.11+ (`<3.13`). Managed with [`uv`](https://docs.astral.sh/uv/).

## Setup

```bash
uv sync --all-extras            # install deps (incl. dev group)
uv run pre-commit install       # install pre-commit hooks
cp .env.example .env            # add ANTHROPIC_API_KEY
```

## Common Commands

```bash
make format        # ruff format
make lint          # ruff check
make check         # format-check + lint  (run before committing)
make fix           # auto-fix + format
make test          # pytest (all tests in tests/)
make sort-authors  # sort authors.yaml alphabetically
```

### Notebook testing

The `tests/` suite parametrizes over notebooks discovered on disk. Selectors are exposed both as Make targets and pytest CLI options.

```bash
# Structure-only (fast, no API calls)
make test-notebooks
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks NOTEBOOK_DIR=capabilities

# Execution (slow, needs ANTHROPIC_API_KEY)
make test-notebooks-exec
make test-notebooks-exec NOTEBOOK=path/to/nb.ipynb

# Isolated tox env / quick (non-pytest) validators
make test-notebooks-tox
make test-notebooks-quick
```

Equivalent direct pytest options (defined in `tests/conftest.py`): `--notebook`, `--notebook-dir`, `--execute-notebooks`, `--notebook-timeout`, `--skip-third-party`, `--registry-only`. Notebook execution tests are marked `slow` and excluded from default `make test-notebooks`.

Standalone validators in `scripts/`:
- `validate_notebooks.py` / `validate_all_notebooks.py` — structural checks
- `validate_authors_sorted.py` — used by `make sort-authors`
- `test_notebooks.py` — quick non-pytest runner (`--list`, `--quick`, `--notebook`, `--dir`)

## Architecture

### Top-level layout

Each top-level directory is a topical bucket of notebooks. Notebook content drives the repo — there is no shared library code.

| Path | Contents |
|---|---|
| `capabilities/` | Core Claude capabilities: classification, RAG, summarization |
| `tool_use/` | Tool-calling patterns, programmatic tool calling, tool search |
| `multimodal/` | Vision, charts, PDFs, sub-agents |
| `extended_thinking/` | Extended-reasoning patterns |
| `misc/` | Batching, prompt caching, JSON mode, moderation, etc. |
| `skills/` | Document-generation skills cookbook (**has its own `CLAUDE.md`** — defer to it for that subtree) |
| `claude_agent_sdk/` | Multi-notebook walkthroughs using the Agent SDK; has subpackages (`research_agent/`, `chief_of_staff_agent/`, …) and its own `pyproject.toml` |
| `coding/` | Frontend / coding-with-Claude prompting guides |
| `observability/` | Usage & cost API examples |
| `patterns/` | Agent design patterns |
| `tool_evaluation/` | Tool-use evaluation harness |
| `finetuning/` | Bedrock fine-tuning |
| `third_party/` | Pinecone, Voyage, ElevenLabs, Wikipedia, etc. integrations |
| `tests/` | Pytest suite + `notebook_tests/` (structure & execution) |
| `scripts/` | Validators (notebooks, authors) |
| `.claude/` | `commands/`, `skills/`, `agents/` shared between local Claude Code and CI |
| `.github/workflows/` | Lint, notebook tests, link/model checks, Claude PR review |

### Cross-cutting metadata

- **`registry.yaml`** — canonical index of published notebooks (title, description, path, authors, date, categories). Schema at `.github/registry_schema.json`. New notebooks **must** have a registry entry.
- **`authors.yaml`** — author profiles. Must stay alphabetically sorted (`make sort-authors`).
- **`pyproject.toml`** — single source for deps and ruff/pytest config. **Use `uv add` / `uv add --dev`; do not edit by hand.**

### Slash commands & CI parity

Commands in `.claude/commands/` are invokable in Claude Code locally **and** run as the same checks in GitHub Actions:

- `/notebook-review` — full notebook quality review
- `/model-check` — verify model IDs are current
- `/link-review` — validate links in markdown/notebooks
- `/add-registry` — add a notebook to `registry.yaml`
- `/review-pr`, `/review-pr-ci`, `/review-issue` — PR/issue review workflows

A `code-reviewer` subagent is defined at `.claude/agents/code-reviewer.md`; the `cookbook-audit` skill at `.claude/skills/cookbook-audit/`.

## Conventions

### Code style
- Line length **100**, double quotes, ruff format.
- Lint rules `E, F, I, W, UP, S, B`. Notebooks additionally ignore `E402` (mid-file imports), `F811` (redefinitions), `N803`/`N806` (uppercase var/arg names common in API responses).

### Models — current aliases only
Use **non-dated** aliases:
- Sonnet: `claude-sonnet-4-6`
- Haiku: `claude-haiku-4-5`
- Opus: `claude-opus-4-6`

Bedrock IDs use a different format (only Opus 4.6+ supports the non-dated form):
- `anthropic.claude-opus-4-6-v1`
- `anthropic.claude-sonnet-4-5-20250929-v1:0`
- `anthropic.claude-haiku-4-5-20251001-v1:0`
- Prefix with `global.` for global endpoints (recommended).

`/model-check` enforces this in CI.

### API keys
Always `os.environ.get("ANTHROPIC_API_KEY")`. Never commit `.env`.

### Notebooks
- One concept per notebook; runs top-to-bottom without errors.
- **Keep outputs** — they document expected behavior.
- New notebook → file in the right top-level dir → entry in `registry.yaml` → author entry in `authors.yaml` if new contributor.

### Git
- Branches: `<username>/<feature-description>`
- Conventional commits: `feat(scope): …`, `fix(scope): …`, `docs(scope): …`, `style: …`, `refactor: …`, `test: …`, `chore: …`, `ci: …`
- Run `make check` before committing; pre-commit hooks enforce it.
