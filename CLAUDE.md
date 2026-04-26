# Claude Cookbooks

A collection of Jupyter notebooks and Python examples for building with the Claude API and the Claude Agent SDK.

## Quick Start

```bash
# Install dependencies (Python 3.11 or 3.12 required)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set up API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Development Commands

```bash
make format               # Format code with ruff
make lint                 # Run linting
make check                # format-check + lint (run before committing)
make fix                  # Auto-fix issues + format
make test                 # Run pytest

# Notebook testing
make test-notebooks       # Structure tests (fast, no API calls)
make test-notebooks-exec  # Execution tests (slow, requires API key)
make test-notebooks-tox   # Run in isolated tox environment
make test-notebooks-quick # Quick validation without pytest

# Target a single notebook or directory
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks NOTEBOOK_DIR=capabilities

make sort-authors         # Sort authors.yaml alphabetically
make clean                # Remove cache files
```

Direct `uv` equivalents work too: `uv run ruff format .`, `uv run ruff check --fix .`, `uv run pre-commit run --all-files`.

## Code Style

- **Line length:** 100 characters
- **Quotes:** Double quotes
- **Formatter / linter:** Ruff (rules `E, F, I, W, UP, S, B`; see `pyproject.toml`)
- **Notebooks** have relaxed rules for mid-file imports (E402), redefinitions (F811), and variable naming (N803, N806).

## Git Workflow

**Branch naming:** `<username>/<feature-description>` (e.g., `alice/add-rag-example`)

**Conventional commits:**
```
feat(scope): add new feature
fix(scope): fix bug
docs(scope): update documentation
style: lint/format
refactor: code restructuring
test: tests
chore: maintenance
ci: CI/CD changes
```

## Key Rules

1. **API keys:** Never commit `.env` files. Always read with `os.environ.get("ANTHROPIC_API_KEY")`.

2. **Dependencies:** Use `uv add <package>` or `uv add --dev <package>`. Don't edit `pyproject.toml` directly.

3. **Models — use current Claude models, not dated IDs:**
   - Sonnet: `claude-sonnet-4-6`
   - Haiku: `claude-haiku-4-5`
   - Opus: `claude-opus-4-6`
   - **Never** use dated IDs like `claude-sonnet-4-6-20250514`. Always use the non-dated alias.
   - **Bedrock** uses different IDs:
     - Opus 4.6: `anthropic.claude-opus-4-6-v1`
     - Sonnet 4.5: `anthropic.claude-sonnet-4-5-20250929-v1:0`
     - Haiku 4.5: `anthropic.claude-haiku-4-5-20251001-v1:0`
     - Prepend `global.` for global endpoints (recommended): `global.anthropic.claude-opus-4-6-v1`
     - Bedrock models prior to Opus 4.6 require dated IDs.

4. **Notebooks:**
   - **Keep outputs** — they demonstrate expected results and are intentionally checked in.
   - One concept per notebook; clear narrative markdown cells.
   - Must run top-to-bottom without errors.
   - Use minimal tokens for examples to keep costs low.

5. **Quality checks:** Run `make check` before committing. Pre-commit hooks run ruff + notebook structure validation + authors-sorted check.

## Slash Commands

Defined in `.claude/commands/` and used both in Claude Code locally and in CI:

- `/notebook-review` — Comprehensive notebook quality check
- `/model-check` — Validate Claude model references are current
- `/link-review` — Validate links in markdown and notebooks
- `/add-registry` — Add a new notebook entry to `registry.yaml`
- `/review-pr` — Review an open pull request
- `/review-pr-ci` — Review a PR and post the review (CI/automated use)
- `/review-issue` — Review and respond to a GitHub issue

## Subagents and Skills

- **`.claude/agents/code-reviewer.md`** — Subagent for reviewing notebook/script changes (Python/Jupyter best practices and project standards). Use proactively after significant code changes.
- **`.claude/skills/cookbook-audit/`** — Skill for auditing a notebook against the cookbook rubric. Has its own `SKILL.md`, `style_guide.md`, and `validate_notebook.py`.
- **`skills/CLAUDE.md`** — Nested Claude Code guide for the Skills (document generation) cookbook, including beta-API gotchas for the Files API and `client.beta.*` namespace. Read it before editing anything under `skills/`.
- **`skills/custom_skills/`** — Demonstration skills shipped with the Skills cookbook: `analyzing-financial-statements`, `applying-brand-guidelines`, `creating-financial-models`, `email-workflow-manager`. Each has its own `SKILL.md`.

## Project Structure

```
capabilities/         # Core Claude capabilities: classification, RAG, summarization,
                      #   contextual-embeddings, text-to-sql (each has guide.ipynb +
                      #   data/ + evaluation/)
claude_agent_sdk/     # Tutorial series for the Claude Agent SDK (research,
                      #   chief-of-staff, observability, SRE agents)
coding/               # Coding-focused notebooks (e.g., frontend aesthetics)
extended_thinking/    # Extended reasoning patterns
finetuning/           # Fine-tuning examples (e.g., on Bedrock)
misc/                 # Batch processing, prompt caching, evals, JSON mode,
                      #   citations, PDF, session memory compaction, etc.
multimodal/           # Vision, charts/PPT, transcription, sub-agents, crop tool
observability/        # Usage / Cost API examples
patterns/agents/      # Agent design patterns: basic_workflows.ipynb,
                      #   evaluator_optimizer.ipynb, orchestrator_workers.ipynb (+ prompts/)
skills/               # Skills feature for document generation (xlsx/pptx/pdf/docx)
third_party/          # Integrations: Pinecone, VoyageAI, Wikipedia, MongoDB,
                      #   LlamaIndex, Deepgram, ElevenLabs, WolframAlpha
tool_use/             # Tool use patterns: parallel, choice, structured JSON, memory,
                      #   tool search w/ embeddings, programmatic tool calling, vision
tool_evaluation/      # Tool evaluation framework example
tests/                # Repo-wide pytest tests (conftest.py + notebook_tests/)
tests/notebook_tests/ # Notebook structure + execution tests (nbval/nbconvert based)
scripts/              # Validation scripts (validate_notebooks.py, validate_all_notebooks.py,
                      #   test_notebooks.py, validate_authors_sorted.py, detect-secrets/)
.claude/              # Slash commands, subagents, skills for Claude Code + CI
.github/workflows/    # CI: lint-format, notebook-tests, notebook-quality,
                      #   notebook-diff-comment, links, verify-authors, claude-pr-review,
                      #   claude-model-check, claude-link-review
registry.yaml         # Catalog of notebooks (title, path, authors, categories, date)
authors.yaml          # Contributor metadata (kept sorted; enforced by hook)
pyproject.toml        # Project deps + ruff/pytest config (do not edit directly — use uv)
uv.toml / uv.lock     # uv resolver settings + lockfile
tox.ini               # Isolated tox envs for notebook testing (used by test-notebooks-tox)
lychee.toml           # Link-checker config (used by links.yml CI)
.pre-commit-config.yaml  # Pre-commit hooks: ruff, notebook validation, authors-sorted
```

## Adding a New Cookbook

1. Create the notebook in the appropriate top-level directory.
2. Add an entry to `registry.yaml` with `title`, `description`, `path`, `authors`, `categories`, `date`. (Use `/add-registry` to scaffold.)
3. Add author info to `authors.yaml` if you're a new contributor (`make sort-authors` keeps it sorted).
4. Run `make check` and `make test-notebooks` to validate.
5. Open a PR — CI will run lint, notebook structure tests, model check, link check, and Claude review.

## CI Overview

PRs trigger:
- `lint-format.yml` — ruff format + lint on changed Python/notebooks
- `notebook-tests.yml` — pytest structure tests against changed notebooks
- `notebook-quality.yml` + `notebook-diff-comment.yml` — Claude-driven review on diffs
- `verify-authors.yml` — authors.yaml sorted + registry author references valid
- `links.yml` / `claude-link-review.yml` — link validation
- `claude-model-check.yml` — confirm model IDs match current aliases
- `claude-pr-review.yml` — overall Claude review
