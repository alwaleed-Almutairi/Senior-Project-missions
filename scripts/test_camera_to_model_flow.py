import argparse
import subprocess
import sys
import time
from pathlib import Path

from validation_common import DEFAULT_CAPTURE_DIR, DEFAULT_MODEL_PATH, DEFAULT_OUTPUT_DIR, ensure_dir


def run_step(command):
    print(f"[RUN] {' '.join(command)}")
    started = time.perf_counter()
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")
    return round((time.perf_counter() - started) * 1000.0, 2)


def main():
    parser = argparse.ArgumentParser(description="Local end-to-end validation: RealSense capture -> saved images -> model inference.")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH), help="Path to YOLO model weights.")
    parser.add_argument("--capture-dir", default=str(DEFAULT_CAPTURE_DIR), help="Directory where camera test images will be saved.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory for inference outputs.")
    parser.add_argument("--width", type=int, default=640, help="Color and depth stream width.")
    parser.add_argument("--height", type=int, default=480, help="Color and depth stream height.")
    parser.add_argument("--fps", type=int, default=30, help="Camera FPS.")
    parser.add_argument("--num-images", type=int, default=1, help="Number of images to capture.")
    parser.add_argument("--warmup-frames", type=int, default=60, help="Warm-up frames before capture.")
    parser.add_argument("--delay-s", type=float, default=0.5, help="Delay between captures.")
    parser.add_argument("--auto-exposure", default=None, help="Forwarded auto exposure setting: on/off.")
    parser.add_argument("--exposure", type=float, default=None, help="Forwarded manual exposure value.")
    parser.add_argument("--gain", type=float, default=None, help="Forwarded gain value.")
    parser.add_argument("--brightness", type=float, default=None, help="Forwarded brightness value.")
    parser.add_argument("--contrast", type=float, default=None, help="Forwarded contrast value.")
    parser.add_argument("--sharpness", type=float, default=None, help="Forwarded sharpness value.")
    parser.add_argument("--saturation", type=float, default=None, help="Forwarded saturation value.")
    parser.add_argument("--save-comparison-sheet", action="store_true", help="Save comparison sheet during the capture phase.")
    parser.add_argument("--no-preview", action="store_true", help="Disable live preview in the capture phase.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold for inference.")
    args = parser.parse_args()

    capture_dir = ensure_dir(Path(args.capture_dir).expanduser().resolve())
    output_dir = ensure_dir(Path(args.output_dir).expanduser().resolve())
    scripts_dir = Path(__file__).resolve().parent

    capture_script = scripts_dir / "test_camera_realsense.py"
    model_script = scripts_dir / "test_model_on_images.py"
    capture_command = [
        sys.executable,
        str(capture_script),
        "--output-dir",
        str(capture_dir),
        "--width",
        str(args.width),
        "--height",
        str(args.height),
        "--fps",
        str(args.fps),
        "--num-images",
        str(args.num_images),
        "--warmup-frames",
        str(args.warmup_frames),
        "--delay-s",
        str(args.delay_s),
    ]

    optional_capture_args = [
        ("--auto-exposure", args.auto_exposure),
        ("--exposure", args.exposure),
        ("--gain", args.gain),
        ("--brightness", args.brightness),
        ("--contrast", args.contrast),
        ("--sharpness", args.sharpness),
        ("--saturation", args.saturation),
    ]
    for flag, value in optional_capture_args:
        if value is not None:
            capture_command.extend([flag, str(value)])
    if args.save_comparison_sheet:
        capture_command.append("--save-comparison-sheet")
    if args.no_preview:
        capture_command.append("--no-preview")

    try:
        capture_ms = run_step(capture_command)
        model_ms = run_step(
            [
                sys.executable,
                str(model_script),
                "--model",
                args.model,
                "--input-dir",
                str(capture_dir),
                "--output-dir",
                str(output_dir),
                "--conf",
                str(args.conf),
            ]
        )
    except Exception as exc:
        print(f"[ERROR] End-to-end validation failed: {exc}")
        sys.exit(1)

    print("-" * 64)
    print("[SUCCESS] Local camera -> model validation completed.")
    print(f"[SUCCESS] Captured images: {capture_dir}")
    print(f"[SUCCESS] Outputs: {output_dir}")
    print(f"[SUCCESS] Capture stage latency: {capture_ms:.2f} ms")
    print(f"[SUCCESS] Model stage latency: {model_ms:.2f} ms")
    print(f"[SUCCESS] End-to-end latency: {capture_ms + model_ms:.2f} ms")
    print("✅ PASS: Combined camera -> model validation completed successfully.")


if __name__ == "__main__":
    main()
