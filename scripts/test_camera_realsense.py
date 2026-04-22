import argparse
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from validation_common import DEFAULT_CAPTURE_DIR, DEFAULT_PREVIEW_DIR, DEFAULT_REPORTS_DIR, ensure_dir, pass_fail_label


WINDOW_NAME = "RealSense Live Preview"


def load_realsense():
    try:
        import pyrealsense2 as rs
    except ImportError as exc:
        print("ERROR: pyrealsense2 is not installed or not available in this Python environment.")
        print(f"DETAIL: {exc}")
        sys.exit(1)
    return rs


def detect_devices(rs):
    context = rs.context()
    devices = context.query_devices()
    found = []
    for device in devices:
        found.append(
            {
                "name": device.get_info(rs.camera_info.name),
                "serial": device.get_info(rs.camera_info.serial_number),
                "firmware": device.get_info(rs.camera_info.firmware_version),
            }
        )
    return found


def find_color_sensor(profile, rs):
    device = profile.get_device()
    sensors = list(device.query_sensors())
    for sensor in sensors:
        try:
            name = sensor.get_info(rs.camera_info.name)
        except Exception:
            name = ""
        if "RGB" in name.upper():
            return sensor
    for sensor in sensors:
        if sensor.supports(rs.option.enable_auto_exposure):
            return sensor
    raise RuntimeError("Could not find a configurable color sensor on the connected RealSense device.")


def parse_auto_exposure(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"on", "true", "1", "yes"}:
        return True
    if normalized in {"off", "false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("Expected one of: on, off, true, false, 1, 0, yes, no")


def apply_sensor_option(sensor, option, value, label: str):
    if value is None:
        return {"label": label, "requested": None, "applied": None, "supported": sensor.supports(option), "status": "SKIPPED"}
    if not sensor.supports(option):
        print(f"[WARN] {label} is not supported by this device/profile. Requested value {value} was skipped.")
        return {"label": label, "requested": value, "applied": None, "supported": False, "status": "UNSUPPORTED"}
    try:
        sensor.set_option(option, float(value))
        applied = sensor.get_option(option)
        print(f"[OK] Applied {label}: requested={value} active={applied}")
        return {"label": label, "requested": value, "applied": applied, "supported": True, "status": "APPLIED"}
    except Exception as exc:
        print(f"[WARN] Failed to apply {label}={value}: {exc}")
        return {"label": label, "requested": value, "applied": None, "supported": True, "status": f"FAILED ({exc})"}


def apply_camera_settings(sensor, rs, args):
    settings_report = []
    settings_report.append(
        apply_sensor_option(
            sensor,
            rs.option.enable_auto_exposure,
            1.0 if args.auto_exposure else 0.0 if args.auto_exposure is not None else None,
            "auto_exposure",
        )
    )
    settings_report.append(apply_sensor_option(sensor, rs.option.exposure, args.exposure, "exposure"))
    settings_report.append(apply_sensor_option(sensor, rs.option.gain, args.gain, "gain"))
    settings_report.append(apply_sensor_option(sensor, rs.option.brightness, args.brightness, "brightness"))
    settings_report.append(apply_sensor_option(sensor, rs.option.contrast, args.contrast, "contrast"))
    settings_report.append(apply_sensor_option(sensor, rs.option.sharpness, args.sharpness, "sharpness"))
    settings_report.append(apply_sensor_option(sensor, rs.option.saturation, args.saturation, "saturation"))
    return settings_report


def print_active_camera_settings(sensor, rs):
    options = [
        ("auto_exposure", rs.option.enable_auto_exposure),
        ("exposure", rs.option.exposure),
        ("gain", rs.option.gain),
        ("brightness", rs.option.brightness),
        ("contrast", rs.option.contrast),
        ("sharpness", rs.option.sharpness),
        ("saturation", rs.option.saturation),
    ]
    print("[INFO] Active camera settings:")
    for label, option in options:
        if sensor.supports(option):
            try:
                print(f"  - {label}: {sensor.get_option(option)}")
            except Exception as exc:
                print(f"  - {label}: unavailable ({exc})")
        else:
            print(f"  - {label}: unsupported")


def show_preview(frame, title: str, enabled: bool):
    if not enabled:
        return -1
    preview = frame.copy()
    cv2.putText(preview, title, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imshow(WINDOW_NAME, preview)
    return cv2.waitKey(1) & 0xFF


def warmup_frames(pipeline, align, frames_to_skip: int, show_live: bool):
    print(f"[INFO] Warming up camera for {frames_to_skip} frame(s)...")
    last_color_image = None
    for idx in range(frames_to_skip):
        frames = pipeline.wait_for_frames(timeout_ms=3000)
        aligned_frames = align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        if not color_frame:
            print(f"[WARN] Warm-up frame {idx + 1} did not contain a color frame.")
            continue
        last_color_image = np.asanyarray(color_frame.get_data())
        show_preview(last_color_image, f"Warm-up {idx + 1}/{frames_to_skip}", show_live)
    if last_color_image is None:
        raise RuntimeError("Camera stream started, but no valid color frames were received during warm-up.")
    return last_color_image


def capture_images(pipeline, align, output_dir: Path, num_images: int, delay_s: float, show_live: bool):
    saved_paths = []
    capture_stats = []
    next_capture_at = time.monotonic()
    while len(saved_paths) < num_images:
        frames = pipeline.wait_for_frames(timeout_ms=3000)
        aligned_frames = align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()
        if not color_frame:
            print(f"[ERROR] Capture {len(saved_paths) + 1}/{num_images}: no color frame received.")
            continue

        color_image = np.asanyarray(color_frame.get_data())
        remaining_s = max(0.0, next_capture_at - time.monotonic())
        preview_title = f"Live | next save in {remaining_s:.1f}s | saved {len(saved_paths)}/{num_images}"
        key = show_preview(color_image, preview_title, show_live)
        if key == ord("q"):
            print("[INFO] Capture loop stopped by user.")
            break

        if time.monotonic() < next_capture_at:
            continue

        index = len(saved_paths) + 1
        output_path = output_dir / f"camera_test_{time.strftime('%Y%m%d_%H%M%S')}_{index:02d}.jpg"

        if not cv2.imwrite(str(output_path), color_image):
            print(f"[ERROR] Failed to save image: {output_path}")
            continue

        center_depth_mm = None
        if depth_frame:
            center_depth_mm = round(
                float(depth_frame.get_distance(color_image.shape[1] // 2, color_image.shape[0] // 2)) * 1000.0,
                2,
            )

        saved_paths.append(output_path)
        print(f"[OK] Saved image {index}/{num_images}: {output_path}")
        if center_depth_mm is not None:
            print(f"[INFO] Capture {index}/{num_images}: center depth = {center_depth_mm:.2f} mm")
        capture_stats.append(
            {
                "path": output_path,
                "resolution": f"{color_image.shape[1]}x{color_image.shape[0]}",
                "center_depth_mm": center_depth_mm,
            }
        )
        next_capture_at = time.monotonic() + max(0.0, delay_s)

    return saved_paths, capture_stats


def write_capture_summary(reports_dir: Path, capture_stats, settings_report, args):
    summary_path = reports_dir / "capture_summary.csv"
    fieldnames = [
        "run_mode",
        "image_path",
        "resolution",
        "center_depth_mm",
        "width",
        "height",
        "fps",
        "warmup_frames",
        "delay_s",
        "setting_label",
        "setting_requested",
        "setting_applied",
        "setting_status",
    ]
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if not capture_stats:
            return summary_path
        first = True
        for image_stat in capture_stats:
            for setting in settings_report if first else [None]:
                row = {
                    "run_mode": args.run_mode,
                    "image_path": str(image_stat["path"]),
                    "resolution": image_stat["resolution"],
                    "center_depth_mm": image_stat["center_depth_mm"],
                    "width": args.width,
                    "height": args.height,
                    "fps": args.fps,
                    "warmup_frames": args.warmup_frames,
                    "delay_s": args.delay_s,
                    "setting_label": setting["label"] if setting else "",
                    "setting_requested": setting["requested"] if setting else "",
                    "setting_applied": setting["applied"] if setting else "",
                    "setting_status": setting["status"] if setting else "",
                }
                writer.writerow(row)
            first = False
    return summary_path


def save_comparison_sheet(preview_dir: Path, image_paths):
    images = [cv2.imread(str(path)) for path in image_paths]
    images = [image for image in images if image is not None]
    if not images:
        return None

    tile_width = 480
    rendered = []
    for index, image in enumerate(images, 1):
        height, width = image.shape[:2]
        scale = tile_width / float(width)
        resized = cv2.resize(image, (tile_width, int(height * scale)))
        cv2.putText(resized, f"Capture {index}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        rendered.append(resized)

    max_height = max(img.shape[0] for img in rendered)
    padded = []
    for img in rendered:
        if img.shape[0] < max_height:
            pad = max_height - img.shape[0]
            img = cv2.copyMakeBorder(img, 0, pad, 0, 0, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        padded.append(img)

    sheet = cv2.hconcat(padded)
    output_path = preview_dir / "comparison_sheet.jpg"
    cv2.imwrite(str(output_path), sheet)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="RealSense camera-only validation: device detect, stream start, warm-up, capture, save.")
    parser.add_argument("--capture-dir", default=str(DEFAULT_CAPTURE_DIR), help="Folder where raw captured images will be saved.")
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR), help="Folder where comparison and preview artifacts will be saved.")
    parser.add_argument("--reports-dir", default=str(DEFAULT_REPORTS_DIR), help="Folder where capture reports will be saved.")
    parser.add_argument("--num-images", type=int, default=1, help="Number of images to capture.")
    parser.add_argument("--warmup-frames", type=int, default=60, help="How many initial frames to discard before capture.")
    parser.add_argument("--width", type=int, default=640, help="Color stream width.")
    parser.add_argument("--height", type=int, default=480, help="Color stream height.")
    parser.add_argument("--fps", type=int, default=30, help="Color stream FPS.")
    parser.add_argument("--warmup", dest="warmup_frames", type=int, help="Alias for --warmup-frames.")
    parser.add_argument("--delay-s", type=float, default=0.5, help="Delay between captures in seconds.")
    parser.add_argument("--auto-exposure", type=parse_auto_exposure, default=None, help="Set auto exposure on/off.")
    parser.add_argument("--exposure", type=float, default=None, help="Manual exposure value, if supported.")
    parser.add_argument("--gain", type=float, default=None, help="Manual gain value, if supported.")
    parser.add_argument("--brightness", type=float, default=None, help="Brightness value, if supported.")
    parser.add_argument("--contrast", type=float, default=None, help="Contrast value, if supported.")
    parser.add_argument("--sharpness", type=float, default=None, help="Sharpness value, if supported.")
    parser.add_argument("--saturation", type=float, default=None, help="Saturation value, if supported.")
    parser.add_argument("--save-comparison-sheet", action="store_true", help="Save a side-by-side image comparison sheet.")
    parser.add_argument("--no-preview", action="store_true", help="Disable the OpenCV live preview window.")
    parser.add_argument(
        "--run-mode",
        default="camera_only",
        choices=["camera_only", "model_only", "camera_to_model_flow"],
        help="Run mode label to write into outputs.",
    )
    args = parser.parse_args()

    if args.num_images < 1:
        print("ERROR: --num-images must be at least 1.")
        sys.exit(1)
    if args.warmup_frames < 0:
        print("ERROR: --warmup-frames cannot be negative.")
        sys.exit(1)

    rs = load_realsense()

    print("=" * 64)
    print("RealSense Camera Validation")
    print("=" * 64)

    devices = detect_devices(rs)
    if not devices:
        print("ERROR: No Intel RealSense device detected.")
        print("CHECK: USB connection, power, permissions, and that no other process is holding the camera.")
        sys.exit(1)

    print(f"[OK] Detected {len(devices)} RealSense device(s):")
    for idx, device in enumerate(devices, 1):
        print(f"  {idx}. {device['name']} | S/N: {device['serial']} | FW: {device['firmware']}")

    capture_dir = ensure_dir(Path(args.capture_dir).expanduser().resolve())
    preview_dir = ensure_dir(Path(args.preview_dir).expanduser().resolve())
    reports_dir = ensure_dir(Path(args.reports_dir).expanduser().resolve())
    print(f"[INFO] Raw captures will be saved to: {capture_dir}")
    print(f"[INFO] Preview artifacts will be saved to: {preview_dir}")
    print(f"[INFO] Reports will be saved to: {reports_dir}")
    show_live = not args.no_preview
    if show_live:
        print("[INFO] Live preview enabled. Press Ctrl+C to stop if needed.")

    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.color, args.width, args.height, rs.format.bgr8, args.fps)
    config.enable_stream(rs.stream.depth, args.width, args.height, rs.format.z16, args.fps)

    try:
        print(f"[INFO] Starting color + depth streams at {args.width}x{args.height} @ {args.fps} FPS...")
        profile = pipeline.start(config)
        align = rs.align(rs.stream.color)
        color_profile = profile.get_stream(rs.stream.color).as_video_stream_profile()
        depth_profile = profile.get_stream(rs.stream.depth).as_video_stream_profile()
        color_sensor = find_color_sensor(profile, rs)
        settings_report = apply_camera_settings(color_sensor, rs, args)
        print_active_camera_settings(color_sensor, rs)
        print(
            f"[INFO] Color stream: {color_profile.width()}x{color_profile.height()} @ {color_profile.fps()} FPS | "
            f"Depth stream: {depth_profile.width()}x{depth_profile.height()} @ {depth_profile.fps()} FPS"
        )
        preview = warmup_frames(pipeline, align, args.warmup_frames, show_live)
        print(f"[OK] Camera stream is live. Last warm-up frame shape: {preview.shape}")
        saved_paths, capture_stats = capture_images(pipeline, align, capture_dir, args.num_images, args.delay_s, show_live)
        summary_path = write_capture_summary(reports_dir, capture_stats, settings_report, args)
        comparison_path = save_comparison_sheet(preview_dir, saved_paths) if args.save_comparison_sheet else None
    except Exception as exc:
        print(f"❌ FAIL: RealSense validation failed: {exc}")
        sys.exit(1)
    finally:
        try:
            pipeline.stop()
            print("[INFO] Camera pipeline stopped cleanly.")
        except Exception:
            pass
        if show_live:
            cv2.destroyAllWindows()

    if not saved_paths:
        print("❌ FAIL: Stream started, but no images were saved successfully.")
        sys.exit(1)

    print(f"[SUCCESS] Saved {len(saved_paths)} image(s).")
    for path in saved_paths:
        print(f"  - {path}")
    print(f"[INFO] Resolution: {capture_stats[0]['resolution']}")
    print(f"[INFO] FPS: {args.fps}")
    if capture_stats[0]["center_depth_mm"] is not None:
        print(f"[INFO] Center depth: {capture_stats[0]['center_depth_mm']:.2f} mm")
    print(f"[INFO] Summary log: {summary_path}")
    if comparison_path is not None:
        print(f"[INFO] Comparison sheet: {comparison_path}")
    print(f"✅ {pass_fail_label(True)}: Camera-only validation completed successfully.")


if __name__ == "__main__":
    main()
