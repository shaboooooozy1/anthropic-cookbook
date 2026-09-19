#!/usr/bin/env bash
# Idempotent Cloud Agent install for the Claude Cookbooks repo.
# Installs uv (if missing) and syncs root project and dev dependencies into .venv.
set -euo pipefail

# uv installs to ~/.local/bin; make sure it is on PATH for this script.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "Using uv $(uv --version)"

# Sync root project extras + the default dev group from the committed lockfile.
# Fail on stale metadata instead of silently changing uv.lock during a Build.
# Nested projects and notebook-specific requirements need their own setup.
uv sync --locked --all-extras

python_version=$(uv run --locked python --version)
echo "Dependencies synced. $python_version"
