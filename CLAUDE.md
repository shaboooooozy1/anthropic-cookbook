# Claude Cookbooks

A collection of Jupyter notebooks and Python examples for building with the Claude API.

## Quick Start

```bash
# Install dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install

# Set up API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

Requires Python 3.11 or 3.12 (`requires-python = ">=3.11,<3.13"`).

## Development Commands

### Code quality

```bash
make format        # Format code with ruff
make lint          # Run linting
make check         # format-check + lint (run before committing)
make fix           # Auto-fix lint issues + format
make test          # Run pytest
```

Or directly with uv:

```bash
uv run ruff format .           # Format
uv run ruff check .            # Lint
uv run ruff check --fix .      # Auto-fix
uv run pre-commit run --all-files
```

### Notebook testing

```bash
make test-notebooks          # Structural tests (fast, no API calls)
make test-notebooks-exec     # Execute notebooks (slow, requires API key)
make test-notebooks-tox      # Run in isolated tox environment
make test-notebooks-quick    # Quick validation script

# Target a single file or directory:
make test-notebooks NOTEBOOK=tool_use/calculator_tool.ipynb
make test-notebooks-tox NOTEBOOK_DIR=capabilities
```

Available `tox` environments (see `tox.ini`): `structure`, `structure-single`, `execution`, `execution-single`, `registry`, `quick`, `third-party`, `lint`, `format`.

### Other

```bash
make sort-authors  # Sort authors.yaml alphabetically
make clean         # Remove cache files
```

## Code Style

- **Line length:** 100 characters
- **Quotes:** Double quotes
- **Formatter / linter:** Ruff (`E`, `F`, `I`, `W`, `UP`, `S`, `B` rules)
- **Target:** Python 3.11

Notebooks have relaxed rules for mid-file imports (E402), redefinitions (F811), and variable naming (N803, N806). See `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml`.

## Git Workflow

**Branch naming:** `<username>/<feature-description>` (e.g. `alice/add-rag-example`)

**Commit format (conventional commits):**
```
feat(scope): add new feature
fix(scope): fix bug
docs(scope): update documentation
style: lint/format
refactor(scope): restructure code
test(scope): add tests
chore: maintenance
ci: CI/CD changes
```

Keep commits atomic and focused. Push with `git push -u origin <branch>` and open a PR.

## Key Rules

1. **API Keys:** Never commit `.env` files. Always read keys from environment: `os.environ.get("ANTHROPIC_API_KEY")`.

2. **Dependencies:** Use `uv add <package>` or `uv add --dev <package>`. Never edit `pyproject.toml` directly.

3. **Models:** Use current Claude models — check docs.anthropic.com for the latest versions.
   - Sonnet: `claude-sonnet-4-6`
   - Haiku: `claude-haiku-4-5`
   - Opus: `claude-opus-4-6`
   - **Never use dated model IDs** (e.g. `claude-sonnet-4-6-20250514`). Always use the non-dated alias.
   - **Bedrock model IDs** follow a different format. Use the base Bedrock model ID from the docs:
     - Opus 4.6: `anthropic.claude-opus-4-6-v1`
     - Sonnet 4.5: `anthropic.claude-sonnet-4-5-20250929-v1:0`
     - Haiku 4.5: `anthropic.claude-haiku-4-5-20251001-v1:0`
     - Prepend `global.` for global endpoints (recommended): `global.anthropic.claude-opus-4-6-v1`
     - Note: Bedrock models before Opus 4.6 require dated IDs in their Bedrock model ID.

4. **Notebooks:**
   - Keep outputs in notebooks (intentional — they demonstrate expected results).
   - One concept per notebook with clear explanations.
   - Notebooks must run top-to-bottom without errors.
   - Use minimal tokens for example API calls.

5. **Quality checks:** Run `make check` before committing. Pre-commit hooks run ruff (lint + format), `scripts/validate_notebooks.py`, and `scripts/validate_authors_sorted.py --fix`.

## Adding a New Cookbook

1. Create the notebook in the appropriate directory.
2. Add an entry to `registry.yaml` with `title`, `description`, `path`, `authors`, `date`, and `categories` (schema: `.github/registry_schema.json`).
3. If the contributor is new, add their info to `authors.yaml` (schema: `.github/authors_schema.json`).
4. Run `make check` and `make test-notebooks NOTEBOOK=<path>`, then submit a PR.

The `/add-registry` slash command can automate steps 2–3.

## Slash Commands

Available in Claude Code (defined in `.claude/commands/`) and reused by GitHub Actions CI:

- `/notebook-review` — Comprehensive notebook quality check
- `/model-check` — Validate Claude model references are current
- `/link-review` — Check links in changed files
- `/review-pr` — Review an open pull request
- `/review-pr-ci` — Review a pull request and post the review (CI variant)
- `/review-issue` — Review and respond to a GitHub issue
- `/add-registry` — Add a new notebook to `registry.yaml`

## Agents and Skills

- `.claude/agents/code-reviewer.md` — Code-review agent for notebooks, GitHub Actions, and scripts.
- `.claude/skills/cookbook-audit/` — Skill for auditing notebooks against a rubric.
- `.github/agents/my-agent.agent.md` — GitHub-hosted agent definition.

## Project Structure

```
capabilities/         # Core Claude capabilities (classification, RAG, summarization, text-to-SQL,
                      # contextual embeddings)
skills/               # Advanced skill-based notebooks and helpers
tool_use/             # Tool use patterns (calculator, customer service, memory tool, parallel
                      # tools, programmatic tool calling, tool search, vision-with-tools, etc.)
tool_evaluation/      # Tool evaluation framework + notebook
multimodal/           # Vision and image processing (best practices, charts, transcription,
                      # sub-agents, crop tool)
extended_thinking/    # Extended reasoning patterns (with and without tool use)
claude_agent_sdk/     # Notebooks and supporting code for the Claude Agent SDK (research, chief
                      # of staff, observability, SRE agents)
coding/               # Coding-focused notebooks (e.g. frontend aesthetics)
patterns/             # Reusable agent patterns
finetuning/           # Fine-tuning examples (e.g. on Bedrock)
observability/        # Usage / cost API examples
misc/                 # Batch, caching, citations, evals, JSON mode, moderation, PDFs, SQL,
                      # session memory, metaprompt, etc.
third_party/          # Third-party integrations: Deepgram, ElevenLabs, LlamaIndex, MongoDB,
                      # Pinecone, VoyageAI, Wikipedia, WolframAlpha
scripts/              # Validation scripts (notebooks, authors, secret detection)
tests/                # pytest suite (notebook structural + execution tests)
.claude/              # Claude Code commands, agents, and skills
.github/              # Workflows, issue templates, PR template, schemas, agents
registry.yaml         # Canonical list of cookbook notebooks (registry_schema.json)
authors.yaml          # Contributor metadata (authors_schema.json)
pyproject.toml        # Project metadata, ruff/pytest config
Makefile              # Common dev tasks
tox.ini               # Isolated test environments
```

## CI

GitHub Actions workflows in `.github/workflows/`:

- `lint-format.yml` — Ruff lint + format check
- `notebook-quality.yml` — Notebook structural validation
- `notebook-tests.yml` — Notebook execution tests (maintainers only)
- `notebook-diff-comment.yml` — Comment notebook diffs on PRs
- `verify-authors.yml` — Validate `authors.yaml` is sorted and well-formed
- `links.yml`, `claude-link-review.yml` — Link validation
- `claude-model-check.yml` — Validate Claude model references
- `claude-pr-review.yml` — Claude-powered PR review

External contributors run a reduced test set to conserve API budget.
