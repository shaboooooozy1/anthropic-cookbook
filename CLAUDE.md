# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

The Claude Cookbooks is a collection of Jupyter notebooks (and a few Python examples) that demonstrate how to build with the Claude API. Notebooks are the primary deliverable: each one teaches a single concept end-to-end with executed outputs preserved in the file. Code in `scripts/`, `tests/`, and `.claude/` exists to validate and review those notebooks.

## Setup

```bash
uv sync --all-extras          # install runtime + dev deps (Python 3.11, <3.13)
uv run pre-commit install     # install hooks (ruff + notebook validation)
cp .env.example .env          # then edit and add ANTHROPIC_API_KEY
```

## Common Commands

```bash
make format    # ruff format
make lint      # ruff check
make check     # format-check + lint (run before committing)
make fix       # ruff --fix + format
make test      # pytest (structural notebook tests, fast)
```

### Notebook tests

Notebooks have two layers of tests, defined in `tests/notebook_tests/` and parameterized via `tests/conftest.py`:

```bash
# Structural validation (no API calls, fast) — what CI runs by default
make test-notebooks
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks NOTEBOOK_DIR=capabilities

# Execution tests (slow, needs ANTHROPIC_API_KEY)
make test-notebooks-exec [NOTEBOOK=...] [NOTEBOOK_DIR=...]

# Same tests in an isolated tox env (matches CI exactly)
make test-notebooks-tox [NOTEBOOK=...] [NOTEBOOK_DIR=...]

# Lightweight non-pytest validation
make test-notebooks-quick [NOTEBOOK=...] [NOTEBOOK_DIR=...]
```

Useful pytest flags (when invoking `uv run pytest tests/notebook_tests/test_notebooks.py` directly): `--notebook`, `--notebook-dir`, `--execute-notebooks`, `--notebook-timeout`, `--skip-third-party`, `--registry-only`. Tests marked `slow` are excluded by default; execution tests are gated behind `--execute-notebooks`.

### Validation scripts

```bash
uv run python scripts/validate_notebooks.py path/to/notebook.ipynb  # structure check (used by pre-commit)
uv run python scripts/validate_all_notebooks.py                     # repo-wide structure check
uv run python scripts/test_notebooks.py --list                      # quick listing/validation tool
uv run python scripts/validate_authors_sorted.py --fix              # sort authors.yaml
```

## Architecture

### Top-level layout

Content directories (each holds notebooks, occasionally a small Python module/`utils/`):

| Directory | Purpose |
| --- | --- |
| `capabilities/` | Core capabilities: classification, contextual embeddings, RAG, summarization, text-to-sql |
| `tool_use/` | Tool use patterns: parallel tools, tool choice, tool search, programmatic tool calling, memory, vision-with-tools |
| `multimodal/` | Vision: image best practices, charts/graphs, transcription, crop tool, sub-agents |
| `extended_thinking/` | Extended thinking, including with tool use |
| `claude_agent_sdk/` | Agent SDK examples (research, chief-of-staff, observability, SRE agents). Has its own `pyproject.toml` |
| `skills/` | Skills feature (xlsx/pptx/pdf/docx generation). Has its own `CLAUDE.md` and `requirements.txt` — read it when working in this directory |
| `coding/` | Coding-specific prompting (e.g. frontend aesthetics) |
| `patterns/agents/` | Reusable agent patterns |
| `tool_evaluation/` | Tool evaluation framework |
| `finetuning/` | Bedrock fine-tuning examples |
| `observability/` | Usage/cost API examples |
| `misc/` | Batch processing, caching, evals, JSON mode, citations, PDF upload, etc. |
| `third_party/` | Integrations: Pinecone, VoyageAI, Wikipedia, MongoDB, ElevenLabs, Deepgram, LlamaIndex, WolframAlpha |

Infrastructure:

- `registry.yaml` — the canonical index of public-facing notebooks (title, description, path, authors, categories, date). Schema: `.github/registry_schema.json`. Verified by `.github/scripts/verify_registry.py`.
- `authors.yaml` — GitHub-username → author display info. Must be alphabetically sorted (pre-commit auto-sorts).
- `tests/notebook_tests/` — pytest-based notebook validation; `conftest.py` adds `--notebook`/`--notebook-dir`/`--execute-notebooks` options and parameterizes tests over discovered notebooks.
- `scripts/` — standalone validators invoked by Makefile, pre-commit, and CI.
- `.claude/` — slash commands, the `cookbook-audit` skill, and the `code-reviewer` agent (use it proactively after non-trivial notebook/script changes).
- `.github/workflows/` — `notebook-tests.yml`, `notebook-quality.yml`, `notebook-diff-comment.yml`, `lint-format.yml`, `links.yml`, `verify-authors.yml`, plus Claude-driven `claude-pr-review.yml`, `claude-link-review.yml`, `claude-model-check.yml`.
- `tox.ini` — isolated environments for `structure`, `structure-single`, `execution`, `execution-single`, `registry` (used by `make test-notebooks-tox`).
- `lychee.toml` — link-checker config used by the `links.yml` workflow.

### How notebook validation fits together

1. **Pre-commit** (`.pre-commit-config.yaml`) runs ruff on `.py`/`.ipynb` and runs `scripts/validate_notebooks.py` on changed notebooks (rejects empty cells and error outputs). It also auto-sorts `authors.yaml`.
2. **`make check`** runs `ruff format --check` + `ruff check`.
3. **CI notebook-tests** runs the pytest structural suite against notebooks changed in the PR.
4. **Slash commands / Claude review workflows** post AI reviews (notebook quality, model usage, links) on PRs.

When you add or modify a notebook, expect all four layers to fire — running `make check` and `make test-notebooks NOTEBOOK=<path>` locally catches the structural issues before pushing.

## Code Style

- Line length 100, double quotes, ruff format/lint (config in `pyproject.toml`).
- Lint rules: `E, F, I, W, UP, S, B`. Notebooks (`*.ipynb`) additionally ignore `E402`, `F811`, `N803`, `N806` (mid-file imports, redefinitions, non-lowercase names are common in pedagogical notebooks).
- Use `uv add <pkg>` / `uv add --dev <pkg>` — do not hand-edit `pyproject.toml` dependencies.

## Models

Always use non-dated aliases (the Claude API model alias resolves to the latest dated version):

- Sonnet: `claude-sonnet-4-6`
- Haiku: `claude-haiku-4-5`
- Opus: `claude-opus-4-6`

**Never** use dated IDs (e.g. `claude-sonnet-4-6-20250514`).

Bedrock model IDs use a different format — use the base Bedrock ID, prepending `global.` for global endpoints:

- Opus 4.6: `anthropic.claude-opus-4-6-v1` (or `global.anthropic.claude-opus-4-6-v1`)
- Sonnet 4.5: `anthropic.claude-sonnet-4-5-20250929-v1:0`
- Haiku 4.5: `anthropic.claude-haiku-4-5-20251001-v1:0`

Bedrock IDs for models *before* Opus 4.6 require dated IDs.

## Notebook Conventions

- One concept per notebook. Test that it runs top-to-bottom without error.
- **Keep cell outputs in the file** — they are intentional documentation. Do not strip them.
- Use `os.environ.get("ANTHROPIC_API_KEY")` (or `dotenv.load_dotenv()`); never hardcode keys.
- Define a `MODEL` constant near the top of the notebook so version bumps are one-line changes.
- Group pip installs (`%pip install -q -U anthropic ...`) and use `%%capture` or `-q` to suppress noisy output.
- Introduce the *problem* before the machinery; list 2–4 learning objectives up front; conclude by mapping back to them.
- See `.claude/agents/code-reviewer.md` for the full notebook-pedagogy checklist used by the in-repo reviewer.

## Adding a New Cookbook

1. Place the notebook in the appropriate top-level directory.
2. Add an entry to `registry.yaml` (title, description, path, authors list, date `YYYY-MM-DD`, categories) — schema at `.github/registry_schema.json`.
3. If you're a new author, add yourself to `authors.yaml` (pre-commit will sort it).
4. Run `make check` and `make test-notebooks NOTEBOOK=<path>` before pushing.

The `/add-registry` slash command automates step 2.

## Slash Commands

Defined in `.claude/commands/`, available in Claude Code and used by CI workflows of the same name:

- `/notebook-review` — full notebook quality review
- `/model-check` — verify Claude model usage is current/non-dated
- `/link-review` — validate links in changed files
- `/add-registry` — add a notebook to `registry.yaml`
- `/review-pr`, `/review-pr-ci`, `/review-issue` — PR / issue review flows

The `cookbook-audit` skill (`.claude/skills/cookbook-audit/`) is the rubric used by `/notebook-review`.

## Git Workflow

- Branch: `<username>/<feature-description>`
- Conventional commits: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `style: ...`, `refactor: ...`, `test: ...`, `chore: ...`, `ci: ...`
