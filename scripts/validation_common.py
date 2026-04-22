import os
import re
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import cv2


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
VALIDATION_DATA_DIR = PROJECT_ROOT / "validation_data"
DEFAULT_MODEL_PATH = MODELS_DIR / "best.pt"
DEFAULT_CAPTURE_DIR = VALIDATION_DATA_DIR / "camera_test"
DEFAULT_OUTPUT_DIR = VALIDATION_DATA_DIR / "test_output"
DOCS_DIR = PROJECT_ROOT / "docs"
CLASS_NAMES = [
    "Corrosion",
    "Settlement",
    "Thermal Expansion",
    "Diagonal Shear",
    "Flexural",
    "Compression",
    "Tension",
    "Torsion",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_existing_dir(path_str: str, label: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"{label} is not a directory: {path}")
    return path


def validate_existing_file(path_str: str, label: str) -> Path:
    path = Path(path_str).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")
    return path


def collect_image_paths(input_dir: Path) -> List[Path]:
    image_paths = [p for p in sorted(input_dir.iterdir()) if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()]
    if not image_paths:
        raise FileNotFoundError(f"No supported image files found in: {input_dir}")
    return image_paths


def parse_ned_from_filename(filename: str) -> Optional[Tuple[float, float, float]]:
    base = Path(filename).stem
    match = re.match(r"^img_([-\d.]+)_([-\d.]+)_([-\d.]+)$", base)
    if not match:
        return None
    return float(match.group(1)), float(match.group(2)), float(match.group(3))


def calc_crack_offset(cx_norm: float, cy_norm: float) -> Tuple[float, float, float]:
    x = 0.0
    y = round((cx_norm - 0.5) * 1.0, 4)
    z = round(-(cy_norm * 1.0 + 0.5), 4)
    return x, y, z


def annotate_detections(image, detections: Iterable[Dict]) -> any:
    annotated = image.copy()
    for det in detections:
        x1, y1, x2, y2 = det["bbox_xyxy"]
        label = f'{det["crack_type"]} {det["confidence"]:.2f}'
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(
            annotated,
            label,
            (x1, max(20, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 220, 0),
            2,
        )
    return annotated


def save_thumbnail_if_possible(image_path: Path, thumbnail_path: Path, max_width: int = 240) -> Optional[Path]:
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        height, width = image.shape[:2]
        if width <= max_width:
            thumb = image
        else:
            scale = max_width / float(width)
            thumb = cv2.resize(image, (int(width * scale), int(height * scale)))
        cv2.imwrite(str(thumbnail_path), thumb)
        return thumbnail_path
    except Exception:
        return None


def now_timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def pass_fail_label(success: bool) -> str:
    return "PASS" if success else "FAIL"
