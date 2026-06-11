#!/bin/bash
set -e

# Set project root to the parent directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Creating venv ==="
python3 -m venv .venv

echo "=== Upgrading pip ==="
.venv/bin/python -m pip install --upgrade pip

echo "=== Installing pytest ==="
.venv/bin/pip install pytest

echo "=== Installing run_workflow dependencies ==="
.venv/bin/pip install -r run_workflow/requirements.txt

echo "=== Installing generate_image_bot dependencies ==="
.venv/bin/pip install -r generate_image_bot/requirements.txt

echo ""
echo "=== Setup complete ==="
echo "To activate the virtual environment, run:"
echo "  source .venv/bin/activate"
