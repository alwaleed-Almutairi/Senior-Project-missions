import argparse
import shutil
import sys
from pathlib import Path

from validation_common import DEFAULT_CAPTURE_DIR, DEFAULT_OUTPUT_DIR, VALIDATION_DATA_DIR, ensure_dir


def clear_directory_contents(path: Path):
    if not path.exists():
        return 0

    removed = 0
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed += 1
    return removed


def main():
    parser = argparse.ArgumentParser(
        description="Delete local validation images and outputs inside validation_data/."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Delete both camera_test and test_output contents.",
    )
    parser.add_argument(
        "--captures-only",
        action="store_true",
        help="Delete only validation_data/camera_test contents.",
    )
    parser.add_argument(
        "--outputs-only",
        action="store_true",
        help="Delete only validation_data/test_output contents.",
    )
    args = parser.parse_args()

    selected_flags = sum([args.all, args.captures_only, args.outputs_only])
    if selected_flags > 1:
        print("ERROR: Choose only one of --all, --captures-only, or --outputs-only.")
        sys.exit(1)

    if args.captures_only:
        targets = [DEFAULT_CAPTURE_DIR]
    elif args.outputs_only:
        targets = [DEFAULT_OUTPUT_DIR]
    else:
        targets = [DEFAULT_CAPTURE_DIR, DEFAULT_OUTPUT_DIR]

    ensure_dir(VALIDATION_DATA_DIR)

    print("=" * 64)
    print("Validation Data Cleanup")
    print("=" * 64)

    total_removed = 0
    for target in targets:
        ensure_dir(target)
        removed = clear_directory_contents(target)
        total_removed += removed
        print(f"[OK] Cleared {removed} item(s) from {target}")

    print("-" * 64)
    print(f"[SUCCESS] Cleanup complete. Removed {total_removed} item(s).")


if __name__ == "__main__":
    main()
