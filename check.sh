#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

for tool in git bash; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: '$tool' is required." >&2
    exit 1
  fi
done

PROJECT_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [[ ! -x "$PROJECT_PYTHON" ]]; then
  PROJECT_PYTHON="python3"
fi
if ! command -v "$PROJECT_PYTHON" >/dev/null 2>&1; then
  echo "Error: Python >= 3.10 is required." >&2
  exit 1
fi
"$PROJECT_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Error: Python >= 3.10 is required.")'

echo "Checking Git changes..."
git --no-pager diff --check
git --no-pager diff --cached --check
if git --no-pager grep -nE '^(<<<<<<< .+|=======|>>>>>>> .+)$' -- .; then
  echo "Error: unresolved merge conflict markers found." >&2
  exit 1
else
  git_status=$?
  if [[ "$git_status" -ne 1 ]]; then
    echo "Error: could not check merge conflict markers." >&2
    exit "$git_status"
  fi
fi

echo "Checking shell syntax..."
bash -n check.sh
sh -n linphone-duck.sh

if ! "$PROJECT_PYTHON" -c 'import pytest' >/dev/null 2>&1; then
  echo "Error: pytest is required. Install requirements-dev.txt in the selected Python environment." >&2
  exit 1
fi

echo "Running tests..."
"$PROJECT_PYTHON" -m pytest tests -v

echo "All checks passed."
