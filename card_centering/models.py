from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ImageMetadata:
    path: Path
    width: int
    height: int
    dpi_x: float | None = None
    dpi_y: float | None = None


@dataclass(frozen=True)
class GuidePositions:
    outer_left: float
    inner_left: float
    inner_right: float
    outer_right: float
    outer_top: float
    inner_top: float
    inner_bottom: float
    outer_bottom: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class AxisMeasurement:
    first_px: float
    second_px: float
    first_percent: float
    second_percent: float
    first_mm: float | None = None
    second_mm: float | None = None

    @property
    def ratio_text(self) -> str:
        return f"{self.first_percent:.1f}/{self.second_percent:.1f}"


@dataclass(frozen=True)
class SideMeasurement:
    horizontal: AxisMeasurement
    vertical: AxisMeasurement


@dataclass(frozen=True)
class MeasurementRecord:
    card_name: str
    front_path: str
    back_path: str
    front: SideMeasurement
    back: SideMeasurement
    front_dpi_x: float | None
    front_dpi_y: float | None
    back_dpi_x: float | None
    back_dpi_y: float | None
    front_rotation_degrees: float = 0.0
    back_rotation_degrees: float = 0.0

    def flat_values(self) -> dict[str, Any]:
        values: dict[str, Any] = {
            "card_name": self.card_name,
            "front_path": self.front_path,
            "back_path": self.back_path,
            "front_dpi_x": self.front_dpi_x,
            "front_dpi_y": self.front_dpi_y,
            "back_dpi_x": self.back_dpi_x,
            "back_dpi_y": self.back_dpi_y,
            "front_rotation_degrees": self.front_rotation_degrees,
            "back_rotation_degrees": self.back_rotation_degrees,
        }
        for side_name, side in (("front", self.front), ("back", self.back)):
            for axis_name, first_name, second_name, axis in (
                ("lr", "left", "right", side.horizontal),
                ("tb", "top", "bottom", side.vertical),
            ):
                values[f"{side_name}_{first_name}_px"] = axis.first_px
                values[f"{side_name}_{second_name}_px"] = axis.second_px
                values[f"{side_name}_{axis_name}_{first_name}_percent"] = axis.first_percent
                values[f"{side_name}_{axis_name}_{second_name}_percent"] = axis.second_percent
                values[f"{side_name}_{first_name}_mm"] = axis.first_mm
                values[f"{side_name}_{second_name}_mm"] = axis.second_mm
        return values

