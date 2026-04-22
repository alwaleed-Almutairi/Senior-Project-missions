# Local Validation Guide

This repo now has a three-phase local validation pipeline that stays inside the project and does not require MAVSDK or the full mission scripts.

## Python Requirements

Install the validation dependencies inside the project virtual environment:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
python -m pip install -r requirements.txt
```

## How To Run Anything In This Repo

For every validation command below, start from a terminal and run:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
```

After that, run the specific script command you want.

## Project Layout

```text
Senior-Project-missions/
├── docs/
│   └── validation_workflow.md
├── models/
│   ├── .gitkeep
│   └── best.pt
├── scripts/
│   ├── cleanup_validation_data.py
│   ├── inference_core.py
│   ├── run_validation_all.sh
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

## Phase 1: Camera Only

Script: `scripts/test_camera_realsense.py`

What it does:

1. Checks that the RealSense D435 is detected over USB.
2. Starts color and depth streams.
3. Warms up for 60 frames by default.
4. Saves raw captures into `validation_data/raw_captures/`.
5. Saves preview and comparison files into `validation_data/previews/`.
6. Saves capture reports into `validation_data/reports/`.
7. Prints resolution, FPS, and center depth.
8. Ends with `PASS` or `FAIL`.
9. Can optionally tune camera clarity settings from the command line.
10. Keeps live preview running while waiting for the next timed capture.

Run:

```bash
python scripts/test_camera_realsense.py
```

Optional live-preview headless override:

```bash
python scripts/test_camera_realsense.py --no-preview
```

Capture every 5 seconds while keeping the preview live:

```bash
python scripts/test_camera_realsense.py --num-images 5 --delay-s 5
```

Press `q` in the preview window to stop early.

Clarity tuning example:

```bash
python scripts/test_camera_realsense.py \
  --width 1280 \
  --height 720 \
  --fps 15 \
  --warmup 60 \
  --num-images 5 \
  --delay-s 5 \
  --auto-exposure on \
  --save-comparison-sheet
```

Notes:

- Unsupported camera options are skipped with a warning instead of crashing the run.
- The script prints the active camera settings before capture.
- The script writes `capture_summary.csv` into `validation_data/reports/`.
- `--save-comparison-sheet` writes `comparison_sheet.jpg` into `validation_data/previews/`.

## Phase 2: Model on Images

Script: `scripts/test_model_on_images.py`

What it does:

1. Loads `models/best.pt`.
2. Scans `validation_data/raw_captures/` for raw images only.
3. Excludes generated files such as `comparison_sheet.jpg` and annotated images from inference input.
4. Runs YOLOv8 on Pi CPU.
5. Records per-image `latency_ms` and total model-processing time.
6. Saves annotated output images into `validation_data/annotated/`.
7. Saves reports into `validation_data/reports/`.
8. Adds `run_mode` to outputs.
9. Uses stable no-detection rows like `<image_stem>_CLEAR`.
10. Uses `LOCAL_VALIDATION_ONLY` placeholders for mission-only coordinate fields when Mission 1 NED is unavailable.
11. Does not include below-threshold detections in final outputs unless `--debug` is enabled.

Run:

```bash
python scripts/test_model_on_images.py
```

Outputs:

- Annotated images: `/home/alled/missions/Senior-Project-missions/validation_data/annotated`
- Per-image CSV: `/home/alled/missions/Senior-Project-missions/validation_data/reports/results.csv`
- Detection CSV: `/home/alled/missions/Senior-Project-missions/validation_data/reports/detections.csv`
- XLSX report: `/home/alled/missions/Senior-Project-missions/validation_data/reports/results.xlsx`

## Phase 3: Camera to Model Combined

Script: `scripts/test_camera_to_model_flow.py`

What it does:

1. Runs the camera capture stage.
2. Saves raw captures into `validation_data/raw_captures/`.
3. Saves previews into `validation_data/previews/`.
4. Runs model inference on those images.
5. Saves annotated outputs into `validation_data/annotated/`.
6. Saves reports into `validation_data/reports/`.
7. Prints capture-stage latency, model-stage latency, and full end-to-end latency.
8. Ends with `PASS` or `FAIL`.

Run:

```bash
python scripts/test_camera_to_model_flow.py
```

Combined flow with camera tuning options:

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

## Recommended Order

1. Run Phase 1 and only continue if it passes.
2. Run Phase 2 and only continue if it passes.
3. Run Phase 3 to validate the full local flow.

## One-Command Full Run

If you want to run cleanup, Phase 1, Phase 2, and Phase 3 in one command:

```bash
bash scripts/run_validation_all.sh
```

## Cleanup

If you want to delete the local test images and generated outputs, run:

```bash
python scripts/cleanup_validation_data.py
```

Optional variants:

```bash
python scripts/cleanup_validation_data.py --captures-only
python scripts/cleanup_validation_data.py --outputs-only
python scripts/cleanup_validation_data.py --all
```

## Notes

- The model path defaults to `models/best.pt`.
- The fuller walkthrough is in `docs/validation_workflow.md`.
- If an image filename matches Mission 1 format like `img_0.00_-1.00_-3.00.jpg`, the detection outputs include Mission 1 style NED-based crack position fields.
- If Mission 1 NED is not available in local validation mode, `drone_N`, `drone_E`, `drone_D`, `abs_x`, `abs_y`, and `abs_z` are filled with `LOCAL_VALIDATION_ONLY`.
- The reusable inference helper for the next Mission 1 integration step is `scripts/inference_core.py`.
