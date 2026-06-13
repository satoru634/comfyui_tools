#!/bin/bash
set -e

# Set project root to the parent directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Creating venv ==="
python3 -m venv .venv

echo "=== Upgrading pip ==="
.venv/bin/python -m pip install --upgrade pip

echo "=== Installing dependencies ==="
.venv/bin/pip install -r requirements.txt

echo ""
echo "=== Setup complete ==="
echo "To activate the virtual environment, run:"
echo "  source .venv/bin/activate"
