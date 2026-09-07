#!/usr/bin/env bash
# Idempotent Cloud Agent install for the Claude Cookbooks repo.
# Installs uv (if missing) and syncs all project dependencies into .venv.
set -euo pipefail

# uv installs to ~/.local/bin; make sure it is on PATH for this script.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Using uv $(uv --version)"

# Create/refresh the virtual environment with all extras + dev dependency group.
# uv sync is idempotent: it is a no-op when the lockfile is already satisfied.
uv sync --all-extras

echo "Dependencies synced. Python $(uv run python --version)"
