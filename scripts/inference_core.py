import sys
import time
from pathlib import Path

from validation_common import CLASS_NAMES, calc_crack_offset, parse_ned_from_filename


LOCAL_VALIDATION_PLACEHOLDER = "LOCAL_VALIDATION_ONLY"


def load_yolo(model_path: Path):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print("ERROR: ultralytics is not installed in this Python environment.")
        print(f"DETAIL: {exc}")
        sys.exit(1)

    print(f"[INFO] Loading model on CPU: {model_path}")
    return YOLO(str(model_path))


def run_inference(model, image_path: Path, conf: float, debug: bool):
    start = time.perf_counter()
    predict_conf = 0.001 if debug else conf
    results = model.predict(source=str(image_path), conf=predict_conf, device="cpu", imgsz=640, verbose=False)
    latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return results[0], latency_ms


def mission_coordinate_fields(image_path: Path, offset_x: float = None, offset_y: float = None, offset_z: float = None):
    ned = parse_ned_from_filename(image_path.name)
    if ned is None:
        return {
            "drone_N": LOCAL_VALIDATION_PLACEHOLDER,
            "drone_E": LOCAL_VALIDATION_PLACEHOLDER,
            "drone_D": LOCAL_VALIDATION_PLACEHOLDER,
            "abs_x": LOCAL_VALIDATION_PLACEHOLDER,
            "abs_y": LOCAL_VALIDATION_PLACEHOLDER,
            "abs_z": LOCAL_VALIDATION_PLACEHOLDER,
            "coordinate_source": "local_validation_placeholder",
        }

    drone_n, drone_e, drone_d = ned
    return {
        "drone_N": drone_n,
        "drone_E": drone_e,
        "drone_D": drone_d,
        "abs_x": round(drone_n + offset_x, 4),
        "abs_y": round(drone_e + offset_y, 4),
        "abs_z": round(drone_d + offset_z, 4),
        "coordinate_source": "mission1_filename_ned",
    }


def extract_detections(result, image_path: Path, latency_ms: float, conf: float, debug: bool, run_mode: str):
    detections = []
    boxes = result.boxes
    accepted_boxes = []

    for box in boxes:
        confidence = float(box.conf[0])
        if debug or confidence >= conf:
            accepted_boxes.append(box)

    num_detections = len(accepted_boxes)

    for det_index, box in enumerate(accepted_boxes, 1):
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        crack_type = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"Unknown_{cls_id}"

        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        cx_norm, cy_norm, width_norm, height_norm = [float(v) for v in box.xywhn[0].tolist()]

        offset_x, offset_y, offset_z = calc_crack_offset(cx_norm, cy_norm)
        coordinate_fields = mission_coordinate_fields(image_path, offset_x, offset_y, offset_z)

        detections.append(
            {
                "detection_id": f"{image_path.stem}_D{det_index:02d}",
                "run_mode": run_mode,
                "image_name": image_path.name,
                "image_path": str(image_path),
                "crack_detected": True,
                "crack_type": crack_type,
                "confidence": round(confidence, 4),
                "passes_conf_threshold": confidence >= conf,
                "latency_ms": latency_ms,
                "num_detections": num_detections,
                "bbox_xyxy": (x1, y1, x2, y2),
                "bbox_x1": x1,
                "bbox_y1": y1,
                "bbox_x2": x2,
                "bbox_y2": y2,
                "bbox_width_px": x2 - x1,
                "bbox_height_px": y2 - y1,
                "cx_norm": round(cx_norm, 6),
                "cy_norm": round(cy_norm, 6),
                "width_norm": round(width_norm, 6),
                "height_norm": round(height_norm, 6),
                "X": offset_x,
                "Y": offset_y,
                "Z": offset_z,
                **coordinate_fields,
            }
        )

    return detections, num_detections


def build_clear_row(image_path: Path, latency_ms: float, run_mode: str):
    coordinate_fields = mission_coordinate_fields(image_path)
    return {
        "detection_id": f"{image_path.stem}_CLEAR",
        "run_mode": run_mode,
        "image_name": image_path.name,
        "image_path": str(image_path),
        "crack_detected": False,
        "crack_type": "",
        "confidence": 0.0,
        "passes_conf_threshold": False,
        "latency_ms": latency_ms,
        "num_detections": 0,
        "bbox_x1": "",
        "bbox_y1": "",
        "bbox_x2": "",
        "bbox_y2": "",
        "bbox_width_px": "",
        "bbox_height_px": "",
        "cx_norm": "",
        "cy_norm": "",
        "width_norm": "",
        "height_norm": "",
        "X": "",
        "Y": "",
        "Z": "",
        **coordinate_fields,
    }
