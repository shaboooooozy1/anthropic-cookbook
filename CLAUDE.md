# Claude Cookbooks

A collection of Jupyter notebooks and Python examples for building with the Claude API. This repository serves as both reference documentation and runnable examples covering RAG, tool use, multimodal, agents, skills, and third-party integrations.

## Quick Start

```bash
# Install dependencies (Python >=3.11,<3.13 required)
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set up API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Development Commands

```bash
make help                     # List all available targets
make format                   # Format code with ruff
make lint                     # Run ruff linting
make check                    # format-check + lint (run before committing)
make fix                      # Auto-fix issues with ruff + format
make test                     # Run pytest
make test-notebooks           # Notebook structure tests (fast, no API calls)
make test-notebooks-exec      # Notebook execution tests (slow, requires API key)
make test-notebooks-tox       # Run notebook tests in isolated tox env
make test-notebooks-quick     # Quick validation without pytest
make sort-authors             # Sort authors.yaml alphabetically
make clean                    # Remove cache files
```

Target a specific notebook or directory via env vars:

```bash
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks NOTEBOOK_DIR=capabilities
```

Or run tools directly with uv:

```bash
uv run ruff format .
uv run ruff check . --fix
uv run pre-commit run --all-files
uv run python scripts/validate_notebooks.py
```

## Code Style

- **Line length:** 100 characters
- **Quotes:** Double quotes
- **Formatter / Linter:** Ruff (covers `.py` and `.ipynb`)
- **Lint rules enabled:** `E, F, I, W, UP, S, B`
- **Globally ignored:** `E501, S101, S301, S311, S608, N806`
- **Notebook-only ignores (`*.ipynb`):** `E402` (mid-file imports), `F811` (redefinitions), `N803`, `N806`

## Git Workflow

- **Branch naming:** `<username>/<feature-description>` (e.g., `alice/add-rag-example`)
- **Conventional commits:** `<type>(<scope>): <description>` — types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `ci`
- **One logical change per commit**, atomic and self-explanatory
- **PR template** at `.github/pull_request_template.md` — fill in summary, motivation, test plan
- Pre-commit hooks (ruff + notebook validators) run automatically; fix issues and re-commit rather than bypassing with `--no-verify`

## Key Rules

1. **API keys:** Never commit `.env`. Load via `dotenv.load_dotenv()` and read with `os.environ.get("ANTHROPIC_API_KEY")`. Never inline `os.environ["ANTHROPIC_API_KEY"] = "sk-..."`.

2. **Dependencies:** Use `uv add <package>` or `uv add --dev <package>`. Never edit `pyproject.toml` by hand. Vet new dependencies before adding.

3. **Models:** Use current Claude models. Always use undated aliases:
   - Sonnet: `claude-sonnet-4-6`
   - Haiku: `claude-haiku-4-5`
   - Opus: `claude-opus-4-6`
   - **Never** use dated IDs like `claude-sonnet-4-6-20250514`.
   - **Bedrock** uses a different format — see docs.claude.com:
     - Opus 4.6: `anthropic.claude-opus-4-6-v1`
     - Sonnet 4.5: `anthropic.claude-sonnet-4-5-20250929-v1:0`
     - Haiku 4.5: `anthropic.claude-haiku-4-5-20251001-v1:0`
     - Prefer global endpoints: prepend `global.` (e.g., `global.anthropic.claude-opus-4-6-v1`).
     - Pre-Opus-4.6 Bedrock IDs require dated suffixes.

4. **Notebooks:**
   - Define a `MODEL` constant at the top so version bumps are one-line changes.
   - **Keep outputs in committed notebooks** — they document expected results.
   - One concept per notebook; problem-focused intros with Terminal Learning Objectives (TLOs) — see `.claude/skills/cookbook-audit/style_guide.md`.
   - Use `%%capture` or `pip -q` for pip installs to keep output clean; group related installs into a single `%pip install -U …` line.
   - Test top-to-bottom execution before committing.

5. **Quality checks:** Run `make check` before committing. CI runs the same checks (`.github/workflows/lint-format.yml`, `notebook-quality.yml`, `notebook-tests.yml`).

## Project Structure

```
capabilities/         # Core Claude capabilities: classification, RAG, contextual embeddings, summarization, text-to-sql
tool_use/             # Tool use patterns: calculator, parallel tools, memory tool, tool search, programmatic tool calling
multimodal/           # Vision: image analysis, charts, transcription, sub-agents, crop tool
extended_thinking/    # Extended reasoning patterns
skills/               # Agent Skills feature (xlsx/pptx/pdf generation); has its own nested CLAUDE.md
claude_agent_sdk/     # Agent SDK examples: research, chief of staff, observability, SRE
patterns/             # Agent design patterns
coding/               # Frontend / coding-focused prompting
finetuning/           # Fine-tuning guides (incl. Bedrock)
observability/        # Usage / cost APIs
tool_evaluation/      # Tool evaluation framework
misc/                 # Batch processing, prompt caching, citations, JSON mode, evals, PDF upload, session memory
third_party/          # Pinecone, VoyageAI, Wikipedia, MongoDB, Deepgram, ElevenLabs, LlamaIndex, WolframAlpha
scripts/              # Validation: validate_notebooks.py, test_notebooks.py, validate_authors_sorted.py, detect-secrets/
tests/                # pytest suite (notebook structure tests under tests/notebook_tests/)
.claude/              # Claude Code config: agents/, commands/, skills/
.github/              # Workflows, agents, PR/issue templates, registry/authors JSON schemas
anthropic_cookbook/   # Empty namespace package (build system placeholder)
registry.yaml         # Catalog of all notebooks (title, description, path, authors, date, categories)
authors.yaml          # Contributor metadata (must stay alphabetically sorted)
Makefile              # Standard dev commands (see above)
pyproject.toml        # Project + ruff + pytest config
tox.ini               # Tox envs for isolated notebook test runs
uv.toml / uv.lock     # uv package manager config + lockfile
lychee.toml           # Link checker config
```

`skills/CLAUDE.md` contains additional, more specific guidance for the Skills cookbook (beta API namespaces, file ID extraction, generation timing notes). Read it when working in `skills/`.

## Slash Commands

Defined in `.claude/commands/` and reused by CI. Available in Claude Code:

- `/notebook-review` — comprehensive notebook quality review
- `/model-check` — validate Claude model references
- `/link-review` — check links in changed files
- `/review-pr` — review an open PR (with optional GitHub posting)
- `/review-pr-ci` — same review, CI-friendly variant that posts back to GitHub
- `/review-issue` — review and respond to a GitHub issue
- `/add-registry` — add a notebook entry to `registry.yaml`

## Subagents and Skills

- **`code-reviewer`** subagent (`.claude/agents/code-reviewer.md`) — invoke proactively after significant code changes; covers Python/Jupyter best practices, security, notebook pedagogy, CI patterns.
- **`cookbook-audit`** skill (`.claude/skills/cookbook-audit/`) — rubric-based notebook audit; reads `style_guide.md` and runs `validate_notebook.py` (which also invokes detect-secrets).

## CI Workflows

Located in `.github/workflows/`:

- `lint-format.yml` — ruff lint + format check on every PR touching Python/notebooks
- `notebook-quality.yml` — notebook structure validation
- `notebook-tests.yml` — pytest-based notebook tests
- `notebook-diff-comment.yml` — PR comment with notebook diffs
- `links.yml` — lychee link check
- `verify-authors.yml` — confirms `authors.yaml` is sorted and registry entries reference real authors
- `claude-link-review.yml`, `claude-model-check.yml`, `claude-pr-review.yml` — Claude-powered PR review jobs

External contributors get reduced API-touching test coverage to conserve quota.

## Adding a New Cookbook

1. Place the notebook in the appropriate directory (e.g., `tool_use/`, `capabilities/`).
2. Add an entry to `registry.yaml` with `title`, `description`, `path`, `authors`, `date`, `categories` (matches `.github/registry_schema.json`).
3. If you're a new contributor, add yourself to `authors.yaml` (matches `.github/authors_schema.json`) and run `make sort-authors`.
4. Run `make check` and `make test-notebooks` (or `/notebook-review`).
5. Open a PR following the template in `.github/pull_request_template.md`.

## Testing Notes

- **Structure tests** (default `make test-notebooks`) are fast, deterministic, no API calls.
- **Execution tests** (`make test-notebooks-exec`) actually run notebooks — require `ANTHROPIC_API_KEY` and can be slow/expensive. Restrict to specific paths via `NOTEBOOK=…` or `NOTEBOOK_DIR=…`.
- **Tox** (`make test-notebooks-tox`) runs the same tests inside an isolated `uv-venv-lock-runner` env, mirroring CI.
- The `slow` pytest marker is excluded by default; pass `--execute-notebooks` to opt in.

## Security

- Never commit secrets. `scripts/detect-secrets/` provides custom plugins + baseline used by the audit skill.
- Report security issues to security@anthropic.com — not via public issues.
