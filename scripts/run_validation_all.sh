#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [[ ! -d "$ROOT_DIR/.venv312" ]]; then
  echo "ERROR: Expected virtual environment not found at $ROOT_DIR/.venv312"
  echo "Create or activate the correct environment before running this script."
  exit 1
fi

source "$ROOT_DIR/.venv312/bin/activate"

echo "================================================================"
echo "Local Validation Pipeline"
echo "================================================================"

echo "[1/4] Cleaning old validation data..."
python scripts/cleanup_validation_data.py

echo "[2/4] Running Phase 1: Camera only..."
python scripts/test_camera_realsense.py

echo "[3/4] Running Phase 2: Model on images..."
python scripts/test_model_on_images.py

echo "[4/4] Running Phase 3: Camera to model combined..."
python scripts/test_camera_to_model_flow.py

echo "----------------------------------------------------------------"
echo "All validation phases completed successfully."
