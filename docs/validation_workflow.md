# Validation Workflow

This document explains the local validation steps in plain order so the camera and model pipeline can be checked safely before using the mission scripts.

## Before Running Any Phase

Open a terminal and start with:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
```

## Phase 1: Camera Only

Script: `scripts/test_camera_realsense.py`

Checks performed:

1. Detects Intel RealSense hardware.
2. Starts both color and depth streams.
3. Aligns depth to color.
4. Applies optional camera tuning settings when supported:
   - auto exposure
   - exposure
   - gain
   - brightness
   - contrast
   - sharpness
   - saturation
5. Prints the active camera settings.
6. Warms up frames.
7. Keeps a live preview running while waiting for timed captures.
8. Captures still image files on the requested interval.
6. Prints:
   - stream resolution
   - configured FPS
   - center depth in mm
   - active settings summary
9. Can save:
   - `capture_summary.csv`
   - `comparison_sheet.jpg`
10. Returns a clear `PASS` or `FAIL`.

Expected output folder:

- `validation_data/camera_test/`

Additional files produced in the capture folder:

- `capture_summary.csv`
- `comparison_sheet.jpg` when `--save-comparison-sheet` is used

Useful camera-only examples:

Default one-image validation:

```bash
python scripts/test_camera_realsense.py
```

Timed capture while keeping the preview live:

```bash
python scripts/test_camera_realsense.py --num-images 5 --delay-s 5
```

Higher-detail comparison profile:

```bash
python scripts/test_camera_realsense.py \
  --width 1280 \
  --height 720 \
  --fps 15 \
  --warmup 60 \
  --num-images 5 \
  --delay-s 1.0 \
  --auto-exposure on \
  --save-comparison-sheet
```

Exact one-line command:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate && cd /home/alled/missions/Senior-Project-missions && python scripts/test_camera_realsense.py --width 1280 --height 720 --fps 15 --warmup 60 --num-images 5 --delay-s 5
```

## Phase 2: Model on Images

Script: `scripts/test_model_on_images.py`

Checks performed:

1. Validates the model path.
2. Validates the input image folder.
3. Runs YOLOv8 inference on CPU with standard Ultralytics resizing.
4. Records per-image latency.
5. Saves annotated images.
6. Saves detection logs to CSV and XLSX.
7. Prints per-image status and an overall summary.

Expected output folder:

- `validation_data/test_output/`

Files produced:

- `results.csv`
- `detections.csv`
- `results.xlsx`
- `annotated/`
- `thumbs/`

Run command:

```bash
python scripts/test_model_on_images.py
```

## Phase 3: Camera to Model Combined

Script: `scripts/test_camera_to_model_flow.py`

Checks performed:

1. Executes the camera-only capture stage.
2. Executes the model-on-images stage.
3. Measures capture-stage runtime.
4. Measures model-stage runtime.
5. Prints the total end-to-end latency.
6. Returns a clear `PASS` or `FAIL`.

Run command:

```bash
python scripts/test_camera_to_model_flow.py
```

Full tuned combined example:

```bash
python scripts/test_camera_to_model_flow.py \
  --model /home/alled/missions/Senior-Project-missions/models/best.pt \
  --capture-dir /home/alled/missions/Senior-Project-missions/validation_data/camera_test \
  --output-dir /home/alled/missions/Senior-Project-missions/validation_data/test_output \
  --width 1280 \
  --height 720 \
  --fps 15 \
  --num-images 5 \
  --warmup-frames 60 \
  --delay-s 5 \
  --auto-exposure on \
  --save-comparison-sheet \
  --conf 0.25
```

## Suggested Run Pattern

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions

python scripts/test_camera_realsense.py
python scripts/test_model_on_images.py
python scripts/test_camera_to_model_flow.py
```

One-command full run:

```bash
bash scripts/run_validation_all.sh
```

Cleanup command:

```bash
python scripts/cleanup_validation_data.py
```

## Organization Notes

- Models stay in `models/`.
- Local validation artifacts stay in `validation_data/`.
- Validation scripts stay in `scripts/`.
- Human-readable guidance stays in `docs/`.
