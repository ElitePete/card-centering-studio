from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .image_processing import LoadedImage
from .measurement import assess_axis
from .models import AxisMeasurement, GuidePositions, SideMeasurement


OUTER_COLOR = "#15d1c5"
INNER_COLOR = "#ff9f1a"
INK = "#172033"
MUTED = "#5d687b"
PANEL_BORDER = "#d9e0ea"
PANEL_BACKGROUND = "#ffffff"
PAGE_BACKGROUND = "#f3f6fa"


@dataclass(frozen=True)
class ReportSide:
    label: str
    image: LoadedImage
    guides: GuidePositions
    measurement: SideMeasurement
    rotation_degrees: float = 0.0


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    fonts = Path("C:/Windows/Fonts")
    choices = (
        ("seguisb.ttf", "segoeui.ttf") if bold else ("segoeui.ttf", "arial.ttf")
    )
    for name in choices:
        path = fonts / name
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default()


def _pil_image(loaded: LoadedImage) -> Image.Image:
    pixels = loaded.pixels_bgra
    if pixels.ndim != 3 or pixels.shape[2] != 4:
        raise ValueError("The report exporter requires a four-channel working image")
    rgba = np.ascontiguousarray(pixels[:, :, [2, 1, 0, 3]])
    return Image.fromarray(rgba, mode="RGBA").convert("RGB")


def _crop_box(side: ReportSide) -> tuple[int, int, int, int]:
    width = side.image.metadata.width
    height = side.image.metadata.height
    guides = side.guides
    card_width = max(1.0, guides.outer_right - guides.outer_left)
    card_height = max(1.0, guides.outer_bottom - guides.outer_top)
    padding = max(24.0, max(card_width, card_height) * 0.04)
    left = max(0, math.floor(guides.outer_left - padding))
    top = max(0, math.floor(guides.outer_top - padding))
    right = min(width, math.ceil(guides.outer_right + padding))
    bottom = min(height, math.ceil(guides.outer_bottom + padding))
    if right <= left or bottom <= top:
        raise ValueError(f"The {side.label.lower()} card guides do not define a usable crop")
    return left, top, right, bottom


def _dashed_line(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    fill: str,
    width: int,
    dash: int = 22,
    gap: int = 14,
) -> None:
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0:
        return
    ux = (x2 - x1) / length
    uy = (y2 - y1) / length
    position = 0.0
    while position < length:
        stop = min(position + dash, length)
        draw.line(
            (
                x1 + ux * position,
                y1 + uy * position,
                x1 + ux * stop,
                y1 + uy * stop,
            ),
            fill=fill,
            width=width,
        )
        position += dash + gap


def _render_annotated_crop(
    side: ReportSide, max_width: int = 1400, max_height: int = 1900
) -> Image.Image:
    source = _pil_image(side.image)
    left, top, right, bottom = _crop_box(side)
    crop = source.crop((left, top, right, bottom))
    scale = min(max_width / crop.width, max_height / crop.height, 1.0)
    target_size = (
        max(1, round(crop.width * scale)),
        max(1, round(crop.height * scale)),
    )
    if target_size != crop.size:
        crop = crop.resize(target_size, Image.Resampling.LANCZOS)

    draw = ImageDraw.Draw(crop)
    line_width = max(3, round(min(crop.width, crop.height) / 300))

    def x(value: float) -> float:
        return (value - left) * scale

    def y(value: float) -> float:
        return (value - top) * scale

    for value in (side.guides.outer_left, side.guides.outer_right):
        draw.line((x(value), 0, x(value), crop.height), fill=OUTER_COLOR, width=line_width)
    for value in (side.guides.outer_top, side.guides.outer_bottom):
        draw.line((0, y(value), crop.width, y(value)), fill=OUTER_COLOR, width=line_width)
    for value in (side.guides.inner_left, side.guides.inner_right):
        _dashed_line(
            draw,
            (x(value), 0),
            (x(value), crop.height),
            fill=INNER_COLOR,
            width=line_width,
        )
    for value in (side.guides.inner_top, side.guides.inner_bottom):
        _dashed_line(
            draw,
            (0, y(value)),
            (crop.width, y(value)),
            fill=INNER_COLOR,
            width=line_width,
        )
    return crop


def _distance_pair(axis: AxisMeasurement, first: str, second: str) -> str:
    text = f"{first}: {axis.first_px:.1f} px    {second}: {axis.second_px:.1f} px"
    if axis.first_mm is not None and axis.second_mm is not None:
        text += f"    ({axis.first_mm:.3f} mm / {axis.second_mm:.3f} mm)"
    return text


def _render_panel(side: ReportSide) -> Image.Image:
    annotated = _render_annotated_crop(side)
    panel_width = 1480
    margin = 40
    title_font = _font(34, bold=True)
    ratio_font = _font(34, bold=True)
    body_font = _font(24)
    badge_font = _font(22, bold=True)
    small_font = _font(20)
    details_height = 360
    panel_height = margin + 48 + 20 + annotated.height + 24 + details_height + margin
    panel = Image.new("RGB", (panel_width, panel_height), PANEL_BACKGROUND)
    draw = ImageDraw.Draw(panel)
    draw.rounded_rectangle(
        (1, 1, panel_width - 2, panel_height - 2),
        radius=18,
        outline=PANEL_BORDER,
        width=3,
    )
    draw.text((margin, margin), side.label.upper(), font=title_font, fill=INK)

    image_x = (panel_width - annotated.width) // 2
    image_y = margin + 68
    panel.paste(annotated, (image_x, image_y))

    horizontal = side.measurement.horizontal
    vertical = side.measurement.vertical
    h_assessment = assess_axis(horizontal)
    v_assessment = assess_axis(vertical)
    y = image_y + annotated.height + 28

    draw.text((margin, y), "LEFT / RIGHT", font=small_font, fill=MUTED)
    draw.text((margin + 210, y - 8), horizontal.ratio_text, font=ratio_font, fill="#2256a8")
    badge = f"{h_assessment.label} · {h_assessment.deviation_points:.1f} points from 50/50"
    draw.text((margin + 520, y), badge, font=badge_font, fill=h_assessment.color)
    y += 50
    draw.text((margin, y), _distance_pair(horizontal, "Left", "Right"), font=body_font, fill=INK)

    y += 72
    draw.line((margin, y - 18, panel_width - margin, y - 18), fill="#e7ebf1", width=2)
    draw.text((margin, y), "TOP / BOTTOM", font=small_font, fill=MUTED)
    draw.text((margin + 210, y - 8), vertical.ratio_text, font=ratio_font, fill="#2256a8")
    badge = f"{v_assessment.label} · {v_assessment.deviation_points:.1f} points from 50/50"
    draw.text((margin + 520, y), badge, font=badge_font, fill=v_assessment.color)
    y += 50
    draw.text((margin, y), _distance_pair(vertical, "Top", "Bottom"), font=body_font, fill=INK)

    y += 62
    dpi = side.image.metadata
    dpi_text = (
        f"DPI metadata: {dpi.dpi_x:.2f} × {dpi.dpi_y:.2f}"
        if dpi.dpi_x and dpi.dpi_y
        else "DPI metadata unavailable — ratios still use pixels"
    )
    draw.text(
        (margin, y),
        f"Straightening correction: {side.rotation_degrees:+.2f}°    ·    {dpi_text}",
        font=small_font,
        fill=MUTED,
    )
    return panel


def render_comparison_report(
    card_name: str,
    front: ReportSide,
    back: ReportSide,
) -> Image.Image:
    """Render both annotated faces and their measurements into one report image."""
    front_panel = _render_panel(front)
    back_panel = _render_panel(back)
    margin = 54
    gap = 38
    header_height = 170
    footer_height = 110
    page_width = margin * 2 + front_panel.width + gap + back_panel.width
    page_height = header_height + max(front_panel.height, back_panel.height) + footer_height
    page = Image.new("RGB", (page_width, page_height), PAGE_BACKGROUND)
    draw = ImageDraw.Draw(page)
    draw.text((margin, 34), card_name, font=_font(46, bold=True), fill=INK)
    created = datetime.now().astimezone().strftime("Exported %Y-%m-%d %H:%M %Z")
    draw.text((margin, 101), created, font=_font(22), fill=MUTED)

    panel_y = header_height
    page.paste(front_panel, (margin, panel_y))
    page.paste(back_panel, (margin + front_panel.width + gap, panel_y))

    footer_y = panel_y + max(front_panel.height, back_panel.height) + 30
    draw.line((margin, footer_y + 17, margin + 46, footer_y + 17), fill=OUTER_COLOR, width=5)
    draw.text((margin + 62, footer_y + 3), "Cyan solid = physical card edge", font=_font(21), fill=INK)
    _dashed_line(
        draw,
        (margin + 430, footer_y + 17),
        (margin + 476, footer_y + 17),
        fill=INNER_COLOR,
        width=5,
        dash=10,
        gap=7,
    )
    draw.text((margin + 492, footer_y + 3), "Amber dashed = printed-image edge", font=_font(21), fill=INK)
    draw.text(
        (page_width - margin - 710, footer_y + 3),
        "Pixel-based centering · millimetres are display-only · no grade prediction",
        font=_font(20),
        fill=MUTED,
    )

    return page


def comparison_report_png_bytes(
    card_name: str,
    front: ReportSide,
    back: ReportSide,
) -> bytes:
    output = BytesIO()
    render_comparison_report(card_name, front, back).save(
        output, format="PNG", dpi=(150, 150), optimize=True
    )
    return output.getvalue()


def retitle_report_png(report_png: bytes, card_name: str) -> bytes:
    """Update the title embedded in a stored report after a history rename."""
    with Image.open(BytesIO(report_png)) as opened:
        page = opened.convert("RGB")
    draw = ImageDraw.Draw(page)
    draw.rectangle((0, 0, page.width, 96), fill=PAGE_BACKGROUND)
    draw.text((54, 34), card_name, font=_font(46, bold=True), fill=INK)
    output = BytesIO()
    page.save(output, format="PNG", dpi=(150, 150), optimize=True)
    return output.getvalue()


def export_comparison_report(
    path: str | Path,
    card_name: str,
    front: ReportSide,
    back: ReportSide,
) -> Path:
    """Export a high-resolution PNG with both annotated faces and measurements."""
    destination = Path(path)
    if destination.suffix.lower() != ".png":
        destination = destination.with_suffix(".png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(comparison_report_png_bytes(card_name, front, back))
    return destination.resolve()
