import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from validation_common import DEFAULT_CAPTURE_DIR, ensure_dir, pass_fail_label


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


def show_preview(frame, title: str, enabled: bool):
    if not enabled:
        return
    preview = frame.copy()
    cv2.putText(preview, title, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imshow(WINDOW_NAME, preview)
    cv2.waitKey(1)


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
    for index in range(1, num_images + 1):
        frames = pipeline.wait_for_frames(timeout_ms=3000)
        aligned_frames = align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()
        if not color_frame:
            print(f"[ERROR] Capture {index}/{num_images}: no color frame received.")
            continue

        color_image = np.asanyarray(color_frame.get_data())
        show_preview(color_image, f"Capture {index}/{num_images}", show_live)
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

        if delay_s > 0 and index < num_images:
            time.sleep(delay_s)

    return saved_paths, capture_stats


def main():
    parser = argparse.ArgumentParser(description="RealSense camera-only validation: device detect, stream start, warm-up, capture, save.")
    parser.add_argument("--output-dir", default=str(DEFAULT_CAPTURE_DIR), help="Folder where captured images will be saved.")
    parser.add_argument("--num-images", type=int, default=1, help="Number of images to capture.")
    parser.add_argument("--warmup-frames", type=int, default=60, help="How many initial frames to discard before capture.")
    parser.add_argument("--width", type=int, default=640, help="Color stream width.")
    parser.add_argument("--height", type=int, default=480, help="Color stream height.")
    parser.add_argument("--fps", type=int, default=30, help="Color stream FPS.")
    parser.add_argument("--delay-s", type=float, default=0.5, help="Delay between captures in seconds.")
    parser.add_argument("--no-preview", action="store_true", help="Disable the OpenCV live preview window.")
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

    output_dir = ensure_dir(Path(args.output_dir).expanduser().resolve())
    print(f"[INFO] Images will be saved to: {output_dir}")
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
        print(
            f"[INFO] Color stream: {color_profile.width()}x{color_profile.height()} @ {color_profile.fps()} FPS | "
            f"Depth stream: {depth_profile.width()}x{depth_profile.height()} @ {depth_profile.fps()} FPS"
        )
        preview = warmup_frames(pipeline, align, args.warmup_frames, show_live)
        print(f"[OK] Camera stream is live. Last warm-up frame shape: {preview.shape}")
        saved_paths, capture_stats = capture_images(pipeline, align, output_dir, args.num_images, args.delay_s, show_live)
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
    print(f"✅ {pass_fail_label(True)}: Camera-only validation completed successfully.")


if __name__ == "__main__":
    main()
