# AGENTS.md

This repo is a collection of Jupyter notebooks and Python helpers for the Claude API and
Claude Agent SDK. See `CLAUDE.md`, `CONTRIBUTING.md`, the `Makefile`, and `pyproject.toml`
for the authoritative dev workflow, code style, and commands.

## Cursor Cloud specific instructions

- Package manager is **uv** (not pip/poetry). It installs to `~/.local/bin`. The startup
  update script installs uv (if missing) and runs `uv sync --all-extras`, which creates the
  `.venv`. Run project commands through `uv run ...` (e.g. `uv run pytest`) or the `make`
  targets, which already wrap `uv run`.
- Standard commands are documented in `CLAUDE.md` / `Makefile`. Key ones: `make check`
  (ruff format-check + lint), `make test` (pytest unit suite), `make test-notebooks`
  (fast notebook structure tests, no API calls).
- **API key required for live notebook execution.** Notebook cells and `make
  test-notebooks-exec` make real Claude API calls and need `ANTHROPIC_API_KEY` in the
  environment (some third-party/embedding notebooks also need `VOYAGE_API_KEY`). Without
  these, dependency install, lint, the unit test suite, and notebook *structure* tests all
  still pass; only live API execution is blocked. `TEST_MODE`/`MAX_TOKENS` in `.env.example`
  are documentation only and are not read by the test harness.
- The "application" is Jupyter. Run the dev server with
  `uv run jupyter lab --no-browser --port 8888 --ip 0.0.0.0 --ServerApp.token="" --ServerApp.password=""`
  and open `http://localhost:8888/lab`. Notebook outputs are intentionally committed to the
  repo, so re-running notebooks will produce diffs — only commit notebook output changes
  intentionally.
