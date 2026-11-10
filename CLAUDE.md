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

See `CONTRIBUTING.md` for the full contributor walkthrough (uv install, pip alternative, troubleshooting). `AGENTS.md` holds agent/Cursor-Cloud-specific notes (e.g. that `TEST_MODE`/`MAX_TOKENS` are documentation only and not read by the test harness, and how to launch Jupyter).

`.env.example` also exposes optional knobs: `CLAUDE_MODEL` (default model used by some notebooks for cost control, e.g. `claude-haiku-4-5`), `TEST_MODE`, `MAX_TOKENS`, `DEBUG`. Note that `TEST_MODE`/`MAX_TOKENS` are documentation-only defaults — the test harness does not read them. Some third-party / embedding notebooks additionally need `VOYAGE_API_KEY`.

## Development Commands

```bash
make help                 # List all available make targets
make format               # Format code with ruff
make lint                 # Run linting
make check                # format-check + lint (run before committing)
make fix                  # Auto-fix issues + format
make install              # uv sync --all-extras
make test                 # Run pytest (unit tests for validators, registry, utils, skills)
make test-cov             # Run pytest with coverage report

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

1. **API Keys:** Never commit `.env` files. Use `dotenv.load_dotenv()` then access keys via `os.environ` or `os.getenv()`

2. **Dependencies:** Use `uv add <package>` or `uv add --dev <package>`. Don't edit `pyproject.toml` directly.

3. **Models:** Use current Claude models. Check platform.claude.com/docs for latest versions.
   - Opus: `claude-opus-5-5`
   - Sonnet: `claude-sonnet-5-5`
   - Fable: `claude-fable-5-1`
   - Haiku: `claude-haiku-5-5`
   - **Never use dated model IDs** (e.g., `claude-sonnet-4-5-20250929`). Always use the non-dated alias.
   - **Bedrock model IDs** follow a different format. Use the base Bedrock model ID from the docs:
     - Opus 5.5: `anthropic.claude-opus-5-5`
     - Sonnet 5.5: `anthropic.claude-sonnet-5-5`
     - Fable 5.1: `anthropic.claude-fable-5-1`
     - Haiku 5.5: `anthropic.claude-haiku-5-5`
     - Prepend `global.` for global endpoints (recommended): `global.anthropic.claude-opus-5-5`
     - Note: these are the IDs for Bedrock's Messages-API endpoint. Integrations that only go through InvokeModel (for example `boto3` `invoke_model`, or fine-tuning jobs) use the dated form instead, e.g. `anthropic.claude-haiku-4-5-20251001-v1:0`.

4. **Notebooks:**
   - **Keep outputs** — they demonstrate expected results and are intentionally checked in.
   - One concept per notebook; clear narrative markdown cells.
   - Must run top-to-bottom without errors.
   - Use minimal tokens for examples to keep costs low.

5. **Quality checks:** Run `make check` before committing. Pre-commit hooks (`.pre-commit-config.yaml`) run `ruff-check --fix`, `ruff-format`, `scripts/validate_notebooks.py` on changed `.ipynb` files, and `scripts/validate_authors_sorted.py --fix` on `authors.yaml`.

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
- **`skills/CLAUDE.md`** — Detailed Claude Code guide for the Skills (document generation) cookbook, including beta-API gotchas for the Files API and `client.beta.*` namespace.

## Project Structure

```
capabilities/      # Core Claude capabilities (RAG, classification, etc.)
evals/             # Model evaluation patterns and benchmarks
skills/            # Advanced skill-based notebooks
tool_use/          # Tool use and integration patterns
multimodal/        # Vision and image processing
misc/              # Batch processing, caching, utilities
third_party/       # Pinecone, Voyage, LlamaIndex integrations
extended_thinking/ # Extended reasoning patterns
scripts/           # Validation scripts
.claude/           # Claude Code commands and skills
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
