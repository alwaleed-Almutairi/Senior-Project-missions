# Validation Workflow

This document explains the local validation steps in plain order so the camera and model pipeline can be checked safely before using the mission scripts.

## Before Running Any Phase

Open a terminal and start with:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
```

## Folder Layout

```text
Senior-Project-missions/
├── models/
│   └── best.pt
├── scripts/
│   ├── inference_core.py
│   ├── test_camera_realsense.py
│   ├── test_model_on_images.py
│   ├── test_camera_to_model_flow.py
│   └── validation_common.py
└── validation_data/
    ├── raw_captures/
    ├── previews/
    ├── annotated/
    └── reports/
```

## Folder Purpose

- `validation_data/raw_captures/`: raw camera images only
- `validation_data/previews/`: generated preview and comparison files
- `validation_data/annotated/`: annotated inference outputs
- `validation_data/reports/`: CSV/XLSX reports and capture summary logs

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
8. Saves raw captures into `validation_data/raw_captures/`.
9. Saves optional comparison sheets into `validation_data/previews/`.
10. Saves capture summary logs into `validation_data/reports/`.
11. Prints:
   - stream resolution
   - configured FPS
   - center depth in mm
   - active settings summary
12. Returns a clear `PASS` or `FAIL`.

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

## Phase 2: Model on Images

Script: `scripts/test_model_on_images.py`

Checks performed:

1. Validates the model path.
2. Validates the raw input image folder.
3. Excludes generated artifacts such as `comparison_sheet.jpg` and annotated images from inference input.
4. Runs YOLOv8 inference on CPU with standard Ultralytics resizing.
5. Records per-image latency and total model-processing time.
6. Keeps one consistent confidence threshold.
7. Does not include below-threshold detections in final CSV/XLSX unless `--debug` is enabled.
8. Uses stable no-detection rows with `<image_stem>_CLEAR`.
9. Adds `run_mode` to outputs.
10. Uses `LOCAL_VALIDATION_ONLY` placeholders for mission-only coordinate fields when Mission 1 NED is unavailable.
11. Saves annotated images into `validation_data/annotated/`.
12. Saves reports into `validation_data/reports/`.

Run command:

```bash
python scripts/test_model_on_images.py
```

Files produced:

- `validation_data/reports/results.csv`
- `validation_data/reports/detections.csv`
- `validation_data/reports/results.xlsx`
- `validation_data/annotated/`
- `validation_data/reports/thumbs/`

## Phase 3: Camera to Model Combined

Script: `scripts/test_camera_to_model_flow.py`

Checks performed:

1. Executes the camera-only capture stage.
2. Saves raw captures into `validation_data/raw_captures/`.
3. Saves previews into `validation_data/previews/`.
4. Executes the model-on-images stage.
5. Saves annotated outputs into `validation_data/annotated/`.
6. Saves reports into `validation_data/reports/`.
7. Measures capture-stage runtime.
8. Measures model-stage runtime.
9. Prints the total end-to-end latency.
10. Returns a clear `PASS` or `FAIL`.

Run command:

```bash
python scripts/test_camera_to_model_flow.py
```

Full tuned combined example:

```bash
python scripts/test_camera_to_model_flow.py \
  --model /home/alled/missions/Senior-Project-missions/models/best.pt \
  --capture-dir /home/alled/missions/Senior-Project-missions/validation_data/raw_captures \
  --preview-dir /home/alled/missions/Senior-Project-missions/validation_data/previews \
  --annotated-dir /home/alled/missions/Senior-Project-missions/validation_data/annotated \
  --reports-dir /home/alled/missions/Senior-Project-missions/validation_data/reports \
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

## Mission 1 Integration Preparation

The validated capture and inference logic is now prepared for Mission 1 integration as follows:

- `scripts/inference_core.py` contains the reusable YOLO loading and detection-extraction logic.
- `mission1_scan.py` can later keep its current flight loop and replace only the simulated detection section with calls into `scripts/inference_core.py`.
- Flight control logic, battery checks, and waypoint movement do not need to change for that next step.
