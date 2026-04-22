import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import pandas as pd

from validation_common import (
    CLASS_NAMES,
    DEFAULT_CAPTURE_DIR,
    DEFAULT_MODEL_PATH,
    DEFAULT_OUTPUT_DIR,
    annotate_detections,
    calc_crack_offset,
    collect_image_paths,
    ensure_dir,
    now_timestamp,
    parse_ned_from_filename,
    pass_fail_label,
    save_thumbnail_if_possible,
    validate_existing_dir,
    validate_existing_file,
)


def load_yolo(model_path: Path):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        print("ERROR: ultralytics is not installed in this Python environment.")
        print(f"DETAIL: {exc}")
        sys.exit(1)

    print(f"[INFO] Loading model on CPU: {model_path}")
    return YOLO(str(model_path))


def run_inference(model, image_path: Path, conf: float):
    start = time.perf_counter()
    results = model.predict(source=str(image_path), conf=conf, device="cpu", imgsz=640, verbose=False)
    latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return results[0], latency_ms


def extract_detections(result, image_path: Path, latency_ms: float):
    detections = []
    boxes = result.boxes
    num_detections = len(boxes)
    ned = parse_ned_from_filename(image_path.name)

    for det_index, box in enumerate(boxes, 1):
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        crack_type = CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else f"Unknown_{cls_id}"

        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
        cx_norm, cy_norm, width_norm, height_norm = [float(v) for v in box.xywhn[0].tolist()]

        offset_x, offset_y, offset_z = calc_crack_offset(cx_norm, cy_norm)
        drone_n = drone_e = drone_d = abs_x = abs_y = abs_z = None
        if ned is not None:
            drone_n, drone_e, drone_d = ned
            abs_x = round(drone_n + offset_x, 4)
            abs_y = round(drone_e + offset_y, 4)
            abs_z = round(drone_d + offset_z, 4)

        detections.append(
            {
                "detection_id": f"{image_path.stem}_D{det_index:02d}",
                "image_name": image_path.name,
                "image_path": str(image_path),
                "crack_detected": True,
                "crack_type": crack_type,
                "confidence": round(confidence, 4),
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
                "drone_N": drone_n,
                "drone_E": drone_e,
                "drone_D": drone_d,
                "abs_x": abs_x,
                "abs_y": abs_y,
                "abs_z": abs_z,
            }
        )

    return detections, num_detections


def build_image_summary(
    image_path: Path,
    latency_ms: float,
    num_detections: int,
    annotated_path: Path,
    status: str,
    crack_types: str,
):
    return {
        "image_name": image_path.name,
        "image_path": str(image_path),
        "annotated_image": str(annotated_path),
        "latency_ms": latency_ms,
        "num_detections": num_detections,
        "status": status,
        "crack_types": crack_types,
        "timestamp": now_timestamp(),
    }


def write_csv(rows, path: Path, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_xlsx(summary_rows, detection_rows, summary_metrics, xlsx_path: Path, thumbs_dir: Path):
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="PerImage", index=False)
        pd.DataFrame(detection_rows).to_excel(writer, sheet_name="Detections", index=False)
        pd.DataFrame(summary_metrics).to_excel(writer, sheet_name="Summary", index=False)

        workbook = writer.book
        ws = writer.sheets["PerImage"]
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 48
        ws.column_dimensions["C"].width = 48
        ws.column_dimensions["D"].width = 14
        ws.column_dimensions["E"].width = 16
        ws.column_dimensions["F"].width = 12
        ws.column_dimensions["G"].width = 24
        ws.column_dimensions["H"].width = 22

        try:
            from openpyxl.drawing.image import Image as XLImage
        except Exception:
            XLImage = None

        if XLImage is not None:
            ws.cell(row=1, column=9, value="thumbnail")
            ws.column_dimensions["I"].width = 42
            for row_index, row in enumerate(summary_rows, start=2):
                thumb_path = save_thumbnail_if_possible(Path(row["annotated_image"]), thumbs_dir / f"thumb_{row_index:03d}.jpg")
                if thumb_path is None:
                    continue
                image = XLImage(str(thumb_path))
                image.width = 180
                image.height = 120
                ws.add_image(image, f"I{row_index}")
                ws.row_dimensions[row_index].height = 95

        ws_summary = writer.sheets["Summary"]
        ws_summary.column_dimensions["A"].width = 32
        ws_summary.column_dimensions["B"].width = 24


def main():
    parser = argparse.ArgumentParser(description="Run YOLO model on saved images and export annotated images + CSV/XLSX.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="Path to YOLO model weights.")
    parser.add_argument("--input-dir", default=str(DEFAULT_CAPTURE_DIR), help="Directory containing input images.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for reports and annotated images.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    args = parser.parse_args()

    try:
        model_path = validate_existing_file(args.model, "Model file")
        input_dir = validate_existing_dir(args.input_dir, "Input image directory")
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    output_dir = ensure_dir(Path(args.output_dir).expanduser().resolve())
    annotated_dir = ensure_dir(output_dir / "annotated")
    thumbs_dir = ensure_dir(output_dir / "thumbs")

    try:
        image_paths = collect_image_paths(input_dir)
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    model = load_yolo(model_path)
    print(f"[INFO] Found {len(image_paths)} image(s) to process in {input_dir}")

    summary_rows = []
    detection_rows = []
    batch_started = time.perf_counter()

    for index, image_path in enumerate(image_paths, 1):
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"[WARN] Skipping unreadable image: {image_path}")
            continue

        print(f"[INFO] [{index}/{len(image_paths)}] Running inference on {image_path.name} ...")
        result, latency_ms = run_inference(model, image_path, args.conf)
        detections, num_detections = extract_detections(result, image_path, latency_ms)
        crack_types = ", ".join(sorted({det["crack_type"] for det in detections})) if detections else ""
        status = pass_fail_label(True)

        annotated_image = annotate_detections(image, detections)
        annotated_path = annotated_dir / f"{image_path.stem}_annotated{image_path.suffix.lower()}"
        cv2.imwrite(str(annotated_path), annotated_image)

        if not detections:
            detection_rows.append(
                {
                    "detection_id": "",
                    "image_name": image_path.name,
                    "image_path": str(image_path),
                    "crack_detected": False,
                    "crack_type": "",
                    "confidence": 0.0,
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
                    "drone_N": "",
                    "drone_E": "",
                    "drone_D": "",
                    "abs_x": "",
                    "abs_y": "",
                    "abs_z": "",
                }
            )
        else:
            detection_rows.extend(
                [
                    {key: value for key, value in det.items() if key != "bbox_xyxy"}
                    for det in detections
                ]
            )

        summary_rows.append(build_image_summary(image_path, latency_ms, num_detections, annotated_path, status, crack_types))
        print(f"[{status}] {image_path.name}: {num_detections} detection(s), {latency_ms:.2f} ms, crack_types={crack_types or 'None'}")

    if not summary_rows:
        print("ERROR: No images were processed successfully.")
        sys.exit(1)

    per_image_csv = output_dir / "results.csv"
    detections_csv = output_dir / "detections.csv"
    results_xlsx = output_dir / "results.xlsx"

    total_detections = sum(row["num_detections"] for row in summary_rows)
    total_inference_ms = round(sum(row["latency_ms"] for row in summary_rows), 2)
    total_processing_ms = round((time.perf_counter() - batch_started) * 1000.0, 2)
    total_processing_s = round(total_processing_ms / 1000.0, 2)
    avg_latency = sum(row["latency_ms"] for row in summary_rows) / len(summary_rows)
    summary_metrics = [
        {"metric": "images_processed", "value": len(summary_rows)},
        {"metric": "total_detections", "value": total_detections},
        {"metric": "average_latency_ms_per_image", "value": round(avg_latency, 2)},
        {"metric": "total_inference_time_ms", "value": total_inference_ms},
        {"metric": "total_batch_processing_time_ms", "value": total_processing_ms},
        {"metric": "total_batch_processing_time_s", "value": total_processing_s},
    ]

    write_csv(summary_rows, per_image_csv, list(summary_rows[0].keys()))
    write_csv(detection_rows, detections_csv, list(detection_rows[0].keys()))
    write_xlsx(summary_rows, detection_rows, summary_metrics, results_xlsx, thumbs_dir)

    print("-" * 64)
    print(f"[SUCCESS] Processed {len(summary_rows)} image(s)")
    print(f"[SUCCESS] Total detections: {total_detections}")
    print(f"[SUCCESS] Average latency: {avg_latency:.2f} ms/image")
    print(f"[SUCCESS] Total inference time: {total_inference_ms:.2f} ms")
    print(f"[SUCCESS] Total batch processing time: {total_processing_ms:.2f} ms ({total_processing_s:.2f} s)")
    print(f"[SUCCESS] Annotated images: {annotated_dir}")
    print(f"[SUCCESS] CSV: {per_image_csv}")
    print(f"[SUCCESS] CSV: {detections_csv}")
    print(f"[SUCCESS] XLSX: {results_xlsx}")
    print(f"✅ {pass_fail_label(True)}: Model-on-images validation completed successfully.")


if __name__ == "__main__":
    main()
