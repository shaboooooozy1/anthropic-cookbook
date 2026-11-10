#!/usr/bin/env bash
# Idempotent Cloud Agent install for the Claude Cookbooks repo.
# Installs uv (if missing) and syncs root project and dev dependencies into .venv.
set -euo pipefail

# uv installs to ~/.local/bin; make sure it is on PATH for this script.
export PATH="$HOME/.local/bin:$PATH"

# Pinned uv release, verified against a checksum vendored here rather than one
# fetched at install time. Piping https://astral.sh/uv/install.sh to sh would
# execute whatever that mutable URL serves; a pinned artifact + vendored hash
# means a changed upstream fails loudly instead of running. Bump all three
# values together when upgrading. The pin targets the Cloud Agent's platform
# (Linux x86_64); on any other machine, install uv yourself before running.
UV_VERSION="0.13.7"
UV_SHA256="c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83"
UV_TARGET="x86_64-unknown-linux-gnu"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing pinned uv ${UV_VERSION}..."
  tmpdir=$(mktemp -d)
  trap 'rm -rf "$tmpdir"' EXIT
  curl -LsSf --proto '=https' --tlsv1.2 \
    -o "$tmpdir/uv.tar.gz" \
    "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_TARGET}.tar.gz"
  echo "${UV_SHA256}  $tmpdir/uv.tar.gz" | sha256sum -c -
  tar -xzf "$tmpdir/uv.tar.gz" -C "$tmpdir"
  mkdir -p "$HOME/.local/bin"
  install -m 0755 "$tmpdir/uv-${UV_TARGET}/uv" "$tmpdir/uv-${UV_TARGET}/uvx" "$HOME/.local/bin/"
fi

echo "Using uv $(uv --version)"

# Sync root project extras + the default dev group from the committed lockfile.
# Fail on stale metadata instead of silently changing uv.lock during a Build.
# Nested projects and notebook-specific requirements need their own setup.
uv sync --locked --all-extras

python_version=$(uv run --locked python --version)
echo "Dependencies synced. $python_version"
