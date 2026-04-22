import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import pandas as pd

from validation_common import (
    DEFAULT_ANNOTATED_DIR,
    DEFAULT_CAPTURE_DIR,
    DEFAULT_MODEL_PATH,
    DEFAULT_REPORTS_DIR,
    annotate_detections,
    collect_image_paths,
    ensure_dir,
    now_timestamp,
    pass_fail_label,
    save_thumbnail_if_possible,
    validate_existing_dir,
    validate_existing_file,
)
from inference_core import build_clear_row, extract_detections, load_yolo, run_inference


def build_image_summary(
    image_path: Path,
    latency_ms: float,
    num_detections: int,
    annotated_path: Path,
    status: str,
    crack_types: str,
    run_mode: str,
):
    return {
        "run_mode": run_mode,
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
    parser.add_argument("--annotated-dir", default=str(DEFAULT_ANNOTATED_DIR), help="Directory for annotated images.")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Directory for CSV/XLSX reports.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--debug", action="store_true", help="Keep below-threshold detections in outputs for debugging.")
    parser.add_argument(
        "--run-mode",
        default="model_only",
        choices=["camera_only", "model_only", "camera_to_model_flow"],
        help="Run mode label to write into outputs.",
    )
    args = parser.parse_args()

    try:
        model_path = validate_existing_file(args.model, "Model file")
        input_dir = validate_existing_dir(args.input_dir, "Input image directory")
    except Exception as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    annotated_dir = ensure_dir(Path(args.annotated_dir).expanduser().resolve())
    reports_dir = ensure_dir(Path(args.reports_dir).expanduser().resolve())
    thumbs_dir = ensure_dir(reports_dir / "thumbs")

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
        result, latency_ms = run_inference(model, image_path, args.conf, args.debug)
        detections, num_detections = extract_detections(result, image_path, latency_ms, args.conf, args.debug, args.run_mode)
        crack_types = ", ".join(sorted({det["crack_type"] for det in detections})) if detections else ""
        status = pass_fail_label(True)

        annotated_image = annotate_detections(image, detections)
        annotated_path = annotated_dir / f"{image_path.stem}_annotated{image_path.suffix.lower()}"
        cv2.imwrite(str(annotated_path), annotated_image)

        if not detections:
            detection_rows.append(build_clear_row(image_path, latency_ms, args.run_mode))
        else:
            detection_rows.extend(
                [
                    {key: value for key, value in det.items() if key != "bbox_xyxy"}
                    for det in detections
                ]
            )

        summary_rows.append(build_image_summary(image_path, latency_ms, num_detections, annotated_path, status, crack_types, args.run_mode))
        print(f"[{status}] {image_path.name}: {num_detections} detection(s), {latency_ms:.2f} ms, crack_types={crack_types or 'None'}")

    if not summary_rows:
        print("ERROR: No images were processed successfully.")
        sys.exit(1)

    per_image_csv = reports_dir / "results.csv"
    detections_csv = reports_dir / "detections.csv"
    results_xlsx = reports_dir / "results.xlsx"

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
    print(f"[SUCCESS] Reports: {reports_dir}")
    print(f"[SUCCESS] CSV: {per_image_csv}")
    print(f"[SUCCESS] CSV: {detections_csv}")
    print(f"[SUCCESS] XLSX: {results_xlsx}")
    print(f"✅ {pass_fail_label(True)}: Model-on-images validation completed successfully.")


if __name__ == "__main__":
    main()
