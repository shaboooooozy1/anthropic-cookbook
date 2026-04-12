# Claude Cookbooks

A collection of Jupyter notebooks and Python examples for building with the Claude API, the Claude Agent SDK, and related tooling.

## Quick Start

```bash
# Install dependencies (Python 3.11-3.12 required)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set up API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Development Commands

```bash
make format                 # Format code with ruff
make lint                   # Run linting
make check                  # Run format-check + lint
make fix                    # Auto-fix issues + format
make test                   # Run pytest
make install                # uv sync --all-extras
make clean                  # Remove cache files
make sort-authors           # Sort authors.yaml alphabetically
```

Notebook testing:

```bash
make test-notebooks             # Structure tests (fast, no API calls)
make test-notebooks-exec        # Execute notebooks (slow, needs API key)
make test-notebooks-tox         # Run tests in isolated tox env
make test-notebooks-quick       # Quick validation via scripts/test_notebooks.py

# Scope a single notebook or directory via env vars:
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks-tox NOTEBOOK_DIR=capabilities
```

Or call `uv` directly:

```bash
uv run ruff format .              # Format
uv run ruff check .               # Lint
uv run ruff check --fix .         # Auto-fix
uv run pre-commit run --all-files
uv run pytest                     # Tests
uv run python scripts/validate_notebooks.py
```

## Code Style

- **Line length:** 100 characters
- **Quotes:** Double quotes
- **Formatter:** Ruff (with native Jupyter support)
- **Target:** `py311`
- **Lint rules enabled:** `E, F, I, W, UP, S, B`
- **Global ignores:** `E501, S101, S301, S311, S608, N806`

Notebooks (`*.ipynb`) have relaxed rules for `E402` (mid-file imports), `F811` (redefinitions), `N803`, and `N806` (variable naming).

## Git Workflow

**Branch naming:** `<username>/<feature-description>` (e.g., `alice/add-rag-example`)

**Conventional commit format:**
```
feat(scope): add new feature
fix(scope): fix bug
docs(scope): update documentation
style: lint/format
refactor(scope): restructure code
test(scope): add/update tests
chore: maintenance
ci: CI/CD changes
```

Keep commits atomic (one logical change each). Never commit `.env` or secrets.

## Key Rules

1. **API Keys:** Never commit `.env` files. Always read via `os.environ.get("ANTHROPIC_API_KEY")`.

2. **Dependencies:** Use `uv add <package>` or `uv add --dev <package>`. Do not edit `pyproject.toml` directly.

3. **Models:** Use current Claude models. Check docs.claude.com for the latest versions.
   - Sonnet: `claude-sonnet-4-6`
   - Haiku: `claude-haiku-4-5`
   - Opus: `claude-opus-4-6`
   - **Never use dated model IDs** (e.g., `claude-sonnet-4-6-20250514`). Always use the non-dated alias.
   - **Bedrock model IDs** follow a different format. Use the base Bedrock model ID from the docs:
     - Opus 4.6: `anthropic.claude-opus-4-6-v1`
     - Sonnet 4.5: `anthropic.claude-sonnet-4-5-20250929-v1:0`
     - Haiku 4.5: `anthropic.claude-haiku-4-5-20251001-v1:0`
     - Prepend `global.` for global endpoints (recommended): `global.anthropic.claude-opus-4-6-v1`
     - Note: Bedrock models before Opus 4.6 require dated IDs in their Bedrock model ID.

4. **Notebooks:**
   - Keep outputs in notebooks (intentional for demonstration).
   - One concept per notebook; clear explanations and comments.
   - Test that notebooks run top-to-bottom without errors.
   - Use minimal tokens in example API calls.

5. **Quality checks:** Run `make check` before committing. Pre-commit hooks run ruff (check + format) and validate notebook structure and `authors.yaml` sorting.

6. **Registry:** When adding a new notebook, add an entry to `registry.yaml` and (if you're a new contributor) add yourself to `authors.yaml`.

## Slash Commands

Defined in `.claude/commands/` and usable both in Claude Code and in CI:

- `/notebook-review` — Comprehensive notebook quality check
- `/model-check` — Verify Claude model references are current
- `/link-review` — Validate links in changed files (also uses `lychee.toml`)
- `/add-registry` — Add a new notebook to `registry.yaml`
- `/review-pr` — Review an open pull request
- `/review-pr-ci` — CI-automated PR review
- `/review-issue` — Review and respond to a GitHub issue

Agents in `.claude/agents/`:
- `code-reviewer` — Cookbook-focused Python/Jupyter code review

Skills in `.claude/skills/`:
- `cookbook-audit` — Rubric-based notebook audit

## Project Structure

```
capabilities/        # Core Claude capabilities (classification, RAG, summarization, text-to-SQL, contextual embeddings)
claude_agent_sdk/    # Claude Agent SDK example agents (research, chief of staff, observability, SRE)
skills/              # Agent Skills (xlsx/pptx/pdf/docx) — has its own CLAUDE.md with details
tool_use/            # Tool use patterns (calculator, parallel tools, memory, tool search, PTC, etc.)
tool_evaluation/     # Tool evaluation notebook and assets
multimodal/          # Vision: getting started, best practices, charts, sub-agents, crop tool
extended_thinking/   # Extended reasoning + extended thinking with tool use
coding/              # Coding-focused notebooks (e.g., frontend aesthetics)
patterns/            # Agent patterns
observability/       # Usage/cost API notebook
finetuning/          # Fine-tuning (e.g., on Bedrock)
misc/                # Batch processing, caching, citations, evals, JSON mode, PDFs, etc.
third_party/         # Integrations: Pinecone, Voyage, Wikipedia, MongoDB, Deepgram, ElevenLabs, LlamaIndex, WolframAlpha
scripts/             # Validation scripts (notebooks, authors, secrets)
tests/               # Pytest suite, including tests/notebook_tests/
.claude/             # Claude Code commands, agents, and skills
.github/workflows/   # CI: lint-format, notebook-quality, notebook-tests, links, model-check, PR review, verify-authors
anthropic_cookbook/  # Dummy package for hatchling build backend
registry.yaml        # Catalog of notebooks (title, description, path, authors, categories)
authors.yaml         # Contributor metadata (kept alphabetically sorted)
pyproject.toml       # Project config, ruff rules, pytest config
Makefile             # Dev command shortcuts
tox.ini              # Isolated notebook test environments
lychee.toml          # Link-checker config
```

Notebooks you modify inside `skills/` should also consult `skills/CLAUDE.md`, which documents Skills-specific beta headers, Files API usage, and common gotchas.

## Testing

Pytest config lives in `pyproject.toml` (`testpaths = ["tests"]`). The `slow` marker gates notebook execution tests that call the API.

- **Structure tests:** `tests/notebook_tests/test_notebooks.py` — validate notebook JSON, imports, and metadata without executing cells.
- **Execution tests:** same file with `--execute-notebooks` — actually runs notebooks; requires `ANTHROPIC_API_KEY`.
- **Quick validation:** `scripts/test_notebooks.py --quick` — lightweight sanity checks.
- **Isolated runs:** `tox` environments (`structure`, `structure-single`) for hermetic testing.

CI runs the equivalent of these under `.github/workflows/notebook-tests.yml` and `notebook-quality.yml`. External contributors have limited API execution to conserve resources.

## Adding a New Cookbook

1. Create the notebook in the appropriate top-level directory.
2. Add an entry to `registry.yaml` with `title`, `description`, `path`, `authors`, `categories`, and `date`.
3. If you're a new contributor, add yourself to `authors.yaml` (run `make sort-authors` to sort).
4. Run `make check` and `make test-notebooks` locally.
5. Commit on a `<username>/<feature>` branch using conventional commits and open a PR.
