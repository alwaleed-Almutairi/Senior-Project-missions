# Validation Workflow

This document explains the local validation steps in plain order so the camera and model pipeline can be checked safely before using the mission scripts.

## Phase 1: Camera Only

Script: `scripts/test_camera_realsense.py`

Checks performed:

1. Detects Intel RealSense hardware.
2. Starts both color and depth streams.
3. Aligns depth to color.
4. Warms up frames.
5. Captures still image files.
6. Prints:
   - stream resolution
   - configured FPS
   - center depth in mm
7. Returns a clear `PASS` or `FAIL`.

Expected output folder:

- `validation_data/camera_test/`

## Phase 2: Model on Images

Script: `scripts/test_model_on_images.py`

Checks performed:

1. Validates the model path.
2. Validates the input image folder.
3. Runs YOLOv8 inference on CPU.
4. Saves annotated images.
5. Saves detection logs to CSV and XLSX.
6. Prints per-image status and an overall summary.

Expected output folder:

- `validation_data/test_output/`

Files produced:

- `results.csv`
- `detections.csv`
- `results.xlsx`
- `annotated/`

## Phase 3: Camera to Model Combined

Script: `scripts/test_camera_to_model_flow.py`

Checks performed:

1. Executes the camera-only capture stage.
2. Executes the model-on-images stage.
3. Measures capture-stage runtime.
4. Measures model-stage runtime.
5. Prints the total end-to-end latency.
6. Returns a clear `PASS` or `FAIL`.

## Suggested Run Pattern

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions

python scripts/test_camera_realsense.py
python scripts/test_model_on_images.py
python scripts/test_camera_to_model_flow.py
```

## Organization Notes

- Models stay in `models/`.
- Local validation artifacts stay in `validation_data/`.
- Validation scripts stay in `scripts/`.
- Human-readable guidance stays in `docs/`.
