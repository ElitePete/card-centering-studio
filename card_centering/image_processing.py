from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PIL import Image

from .models import GuidePositions, ImageMetadata


class ImageLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class LoadedImage:
    pixels_bgra: np.ndarray
    metadata: ImageMetadata


def straightening_correction(dx: float, dy: float) -> float:
    """Angle that rotates a selected card edge onto its nearest image axis."""
    if math.hypot(dx, dy) < 1e-6:
        raise ValueError("The two straightening points must be different")
    selected_angle = math.degrees(math.atan2(dy, dx))
    nearest_axis = round(selected_angle / 90.0) * 90.0
    correction = selected_angle - nearest_axis
    return round(correction, 4)


def _rotation_geometry(
    image: LoadedImage, degrees: float
) -> tuple[np.ndarray, int, int]:
    pixels = image.pixels_bgra
    height, width = pixels.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    cosine = abs(matrix[0, 0])
    sine = abs(matrix[0, 1])
    expanded_width = int(math.ceil(height * sine + width * cosine))
    expanded_height = int(math.ceil(height * cosine + width * sine))
    matrix[0, 2] += expanded_width / 2.0 - center[0]
    matrix[1, 2] += expanded_height / 2.0 - center[1]
    return matrix, expanded_width, expanded_height


def map_point_between_rotations(
    original: LoadedImage,
    point: tuple[float, float],
    from_degrees: float,
    to_degrees: float,
) -> tuple[float, float]:
    """Map a working-canvas point through the original scan to a new rotation."""
    from_matrix, _, _ = _rotation_geometry(original, from_degrees)
    to_matrix, _, _ = _rotation_geometry(original, to_degrees)
    inverse_from = cv2.invertAffineTransform(from_matrix)
    original_point = inverse_from @ np.array([point[0], point[1], 1.0])
    mapped = to_matrix @ np.array([original_point[0], original_point[1], 1.0])
    return float(mapped[0]), float(mapped[1])


def transform_guides_between_rotations(
    original: LoadedImage,
    guides: GuidePositions,
    from_degrees: float,
    to_degrees: float,
) -> GuidePositions:
    """Keep guide reference points attached while fine-tuning scan rotation."""
    center_x = (guides.outer_left + guides.outer_right) / 2.0
    center_y = (guides.outer_top + guides.outer_bottom) / 2.0
    values: dict[str, float] = {}
    for name in ("outer_left", "inner_left", "inner_right", "outer_right"):
        mapped_x, _ = map_point_between_rotations(
            original, (getattr(guides, name), center_y), from_degrees, to_degrees
        )
        values[name] = mapped_x
    for name in ("outer_top", "inner_top", "inner_bottom", "outer_bottom"):
        _, mapped_y = map_point_between_rotations(
            original, (center_x, getattr(guides, name)), from_degrees, to_degrees
        )
        values[name] = mapped_y
    return GuidePositions(**values)


def rotate_scan(image: LoadedImage, degrees: float) -> LoadedImage:
    """Rotate at 1:1 scale on an expanded canvas so no scan pixels are cropped."""
    if abs(degrees) < 1e-9:
        return image

    pixels = image.pixels_bgra
    matrix, expanded_width, expanded_height = _rotation_geometry(image, degrees)
    rotated = cv2.warpAffine(
        pixels,
        matrix,
        (expanded_width, expanded_height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255, 255),
    )
    return LoadedImage(
        pixels_bgra=np.ascontiguousarray(rotated),
        metadata=ImageMetadata(
            path=image.metadata.path,
            width=expanded_width,
            height=expanded_height,
            dpi_x=image.metadata.dpi_x,
            dpi_y=image.metadata.dpi_y,
        ),
    )


def _read_dpi(path: Path) -> tuple[float | None, float | None]:
    try:
        with Image.open(path) as image:
            dpi = image.info.get("dpi")
            if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
                x, y = float(dpi[0]), float(dpi[1])
                return (x if x > 0 else None, y if y > 0 else None)
    except (OSError, TypeError, ValueError):
        pass
    return None, None


def load_scan(path: str | Path) -> LoadedImage:
    """Load a scan with OpenCV while preserving DPI through Pillow metadata."""
    image_path = Path(path)
    try:
        encoded = np.fromfile(image_path, dtype=np.uint8)
    except OSError as exc:
        raise ImageLoadError(f"Could not read {image_path}") from exc

    image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ImageLoadError("The selected file is not a readable image")

    if image.dtype != np.uint8:
        if np.issubdtype(image.dtype, np.integer):
            scale = 255.0 / float(np.iinfo(image.dtype).max)
        else:
            maximum = float(np.nanmax(image))
            scale = 255.0 / maximum if maximum > 0 else 1.0
        image = cv2.convertScaleAbs(image, alpha=scale)

    if image.ndim == 2:
        bgra = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        bgra = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    elif image.shape[2] == 4:
        bgra = image
    else:
        raise ImageLoadError("Unsupported image channel layout")

    dpi_x, dpi_y = _read_dpi(image_path)
    height, width = bgra.shape[:2]
    return LoadedImage(
        pixels_bgra=np.ascontiguousarray(bgra),
        metadata=ImageMetadata(
            path=image_path.resolve(),
            width=width,
            height=height,
            dpi_x=dpi_x,
            dpi_y=dpi_y,
        ),
    )


class CardEdgeDetector(Protocol):
    """Extension point for a future automatic OpenCV detector."""

    def detect(self, image: LoadedImage) -> GuidePositions:
        """Return the eight boundary positions found in *image*."""
        ...


def suggested_manual_guides(width: int, height: int) -> GuidePositions:
    """Provide a neutral starting layout; this is not edge detection."""
    return GuidePositions(
        outer_left=width * 0.02,
        inner_left=width * 0.08,
        inner_right=width * 0.92,
        outer_right=width * 0.98,
        outer_top=height * 0.02,
        inner_top=height * 0.08,
        inner_bottom=height * 0.92,
        outer_bottom=height * 0.98,
    )

