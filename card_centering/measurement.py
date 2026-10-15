from __future__ import annotations

import math
from dataclasses import dataclass

from .models import AxisMeasurement, GuidePositions, SideMeasurement


@dataclass(frozen=True)
class CenteringAssessment:
    label: str
    color: str
    larger_side_percent: float

    @property
    def deviation_points(self) -> float:
        return self.larger_side_percent - 50.0


class InvalidGuidesError(ValueError):
    """Raised when guides do not describe nested outer and inner rectangles."""


def _validate_finite(guides: GuidePositions) -> None:
    for name, value in guides.as_dict().items():
        if not math.isfinite(value):
            raise InvalidGuidesError(f"{name} must be a finite number")


def validate_guides(guides: GuidePositions) -> None:
    _validate_finite(guides)
    if not (
        guides.outer_left <= guides.inner_left <= guides.inner_right <= guides.outer_right
    ):
        raise InvalidGuidesError(
            "Horizontal guides must be ordered outer-left, inner-left, inner-right, outer-right"
        )
    if not (
        guides.outer_top <= guides.inner_top <= guides.inner_bottom <= guides.outer_bottom
    ):
        raise InvalidGuidesError(
            "Vertical guides must be ordered outer-top, inner-top, inner-bottom, outer-bottom"
        )


def pixels_to_mm(pixels: float, dpi: float | None) -> float | None:
    if dpi is None or dpi <= 0:
        return None
    return pixels * 25.4 / dpi


def _axis(first: float, second: float, dpi: float | None) -> AxisMeasurement:
    total = first + second
    if total <= 0:
        raise InvalidGuidesError("Opposing border measurements must have a positive total")
    return AxisMeasurement(
        first_px=first,
        second_px=second,
        first_percent=100.0 * first / total,
        second_percent=100.0 * second / total,
        first_mm=pixels_to_mm(first, dpi),
        second_mm=pixels_to_mm(second, dpi),
    )


def calculate_measurement(
    guides: GuidePositions,
    dpi_x: float | None = None,
    dpi_y: float | None = None,
) -> SideMeasurement:
    """Calculate centering from raw pixel guide positions.

    DPI is used only for the optional millimetre display and never in the ratio
    calculation.
    """
    validate_guides(guides)
    left = guides.inner_left - guides.outer_left
    right = guides.outer_right - guides.inner_right
    top = guides.inner_top - guides.outer_top
    bottom = guides.outer_bottom - guides.inner_bottom
    return SideMeasurement(
        horizontal=_axis(left, right, dpi_x),
        vertical=_axis(top, bottom, dpi_y),
    )


def assess_axis(axis: AxisMeasurement) -> CenteringAssessment:
    """Return a descriptive severity band, never a grading prediction."""
    larger = max(axis.first_percent, axis.second_percent)
    if larger <= 52.0:
        label, color = "Very even", "#147d64"
    elif larger <= 55.0:
        label, color = "Slight offset", "#5f7f28"
    elif larger <= 60.0:
        label, color = "Noticeable offset", "#b66a00"
    elif larger <= 65.0:
        label, color = "Strong offset", "#c34a18"
    else:
        label, color = "Heavy offset", "#b42318"
    return CenteringAssessment(label, color, larger)

