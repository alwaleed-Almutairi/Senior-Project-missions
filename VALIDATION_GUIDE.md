# Local Validation Guide

This repo now has a three-phase local validation pipeline that stays inside the project and does not require MAVSDK or the full mission scripts.

## Python Requirements

Install the validation dependencies inside the project virtual environment:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
python -m pip install -r requirements.txt
```

## Project Layout

```text
Senior-Project-missions/
├── docs/
│   └── validation_workflow.md
├── models/
│   ├── .gitkeep
│   └── best.pt
├── scripts/
│   ├── test_camera_realsense.py
│   ├── test_model_on_images.py
│   ├── test_camera_to_model_flow.py
│   └── validation_common.py
└── validation_data/
    ├── camera_test/
    └── test_output/
```

## Phase 1: Camera Only

Script: `scripts/test_camera_realsense.py`

What it does:

1. Checks that the RealSense D435 is detected over USB.
2. Starts color and depth streams.
3. Warms up for 60 frames by default.
4. Captures one still frame by default.
5. Saves images into `validation_data/camera_test/`.
6. Prints resolution, FPS, and center depth.
7. Ends with `PASS` or `FAIL`.

Run:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
python scripts/test_camera_realsense.py
```

Optional live-preview headless override:

```bash
python scripts/test_camera_realsense.py --no-preview
```

## Phase 2: Model on Images

Script: `scripts/test_model_on_images.py`

What it does:

1. Loads `models/best.pt`.
2. Scans `validation_data/camera_test/` for images.
3. For each image:
   - runs YOLOv8 on Pi CPU
   - records `latency_ms`
   - saves an annotated output image
   - logs image name, crack type, confidence, bounding box, and latency
   - marks the image row as `PASS` if inference completed
4. Writes:
   - `validation_data/test_output/results.csv`
   - `validation_data/test_output/detections.csv`
   - `validation_data/test_output/results.xlsx`
5. Prints total detections, average latency, and overall `PASS`.

Run:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
python scripts/test_model_on_images.py
```

Outputs:

- Annotated images: `/home/alled/missions/Senior-Project-missions/validation_data/test_output/annotated`
- Per-image CSV: `/home/alled/missions/Senior-Project-missions/validation_data/test_output/results.csv`
- Detection CSV: `/home/alled/missions/Senior-Project-missions/validation_data/test_output/detections.csv`
- XLSX report: `/home/alled/missions/Senior-Project-missions/validation_data/test_output/results.xlsx`

## Phase 3: Camera to Model Combined

Script: `scripts/test_camera_to_model_flow.py`

What it does:

1. Runs the camera capture stage.
2. Saves images into `validation_data/camera_test/`.
3. Runs model inference on those images.
4. Saves annotated outputs and reports into `validation_data/test_output/`.
5. Prints capture-stage latency, model-stage latency, and full end-to-end latency.
6. Ends with `PASS` or `FAIL`.

Run:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
python scripts/test_camera_to_model_flow.py
```

## Recommended Order

1. Run Phase 1 and only continue if it passes.
2. Run Phase 2 and only continue if it passes.
3. Run Phase 3 to validate the full local flow.

## Cleanup

If you want to delete the local test images and generated outputs, run:

```bash
source /home/alled/missions/Senior-Project-missions/.venv312/bin/activate
cd /home/alled/missions/Senior-Project-missions
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
- If an image filename matches Mission 1 format like `img_0.00_-1.00_-3.00.jpg`, the detection outputs also include Mission 1 style NED-based crack position fields.
