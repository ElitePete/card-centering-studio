from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QPointF, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .image_processing import (
    ImageLoadError,
    LoadedImage,
    load_scan,
    map_point_between_rotations,
    rotate_scan,
    straightening_correction,
    suggested_manual_guides,
    transform_guides_between_rotations,
)
from .measurement import CenteringAssessment, InvalidGuidesError, assess_axis, calculate_measurement
from .models import GuidePositions, SideMeasurement
from .viewer import GUIDE_ORDER, ImageViewer


DISPLAY_NAMES = {
    "outer_left": "Card left",
    "inner_left": "Print left",
    "inner_right": "Print right",
    "outer_right": "Card right",
    "outer_top": "Card top",
    "inner_top": "Print top",
    "inner_bottom": "Print bottom",
    "outer_bottom": "Card bottom",
}


def _distance_text(name: str, pixels: float, millimetres: float | None) -> str:
    mm_text = f"  •  {millimetres:.3f} mm" if millimetres is not None else ""
    return f"{name}: {pixels:.1f} px{mm_text}"


def _direction_text(first_px: float, second_px: float, axis: str) -> str:
    difference = abs(first_px - second_px)
    if difference < 0.05:
        return "The opposing borders are effectively even."
    if axis == "horizontal":
        wider = "Left" if first_px > second_px else "Right"
        shift = "right" if first_px > second_px else "left"
    else:
        wider = "Top" if first_px > second_px else "Bottom"
        shift = "lower" if first_px > second_px else "higher"
    return f"{wider} border is {difference:.1f} px wider; the printed image sits {shift}."


def _assessment_style(assessment: CenteringAssessment) -> str:
    return (
        f"background: {assessment.color}; color: white; border-radius: 5px; "
        "padding: 5px 8px; font-weight: 600;"
    )


class SideEditor(QWidget):
    imageLoaded = Signal()
    measurementChanged = Signal()

    def __init__(self, side_name: str, parent=None):
        super().__init__(parent)
        self.side_name = side_name
        self.original_loaded: LoadedImage | None = None
        self.loaded: LoadedImage | None = None
        self.rotation_degrees = 0.0
        self.viewer = ImageViewer()
        self.spinboxes: dict[str, QDoubleSpinBox] = {}
        self.image_only_controls: list[QWidget] = []

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.viewer)
        splitter.addWidget(self._build_controls())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 350])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.viewer.guideMoved.connect(self._guide_moved)
        self.viewer.guidesChanged.connect(self._update_results)
        self.viewer.straightenLineSelected.connect(self._straighten_from_line)
        self.viewer.straightenPointCountChanged.connect(self._straighten_point_count_changed)
        self._set_controls_enabled(False)

    def _build_controls(self) -> QWidget:
        contents = QWidget()
        contents.setMinimumWidth(330)
        layout = QVBoxLayout(contents)
        layout.setContentsMargins(12, 12, 12, 12)

        load_button = QPushButton(f"Import {self.side_name} PNG…")
        load_button.setObjectName("primaryButton")
        load_button.clicked.connect(self.choose_image)
        layout.addWidget(load_button)

        self.file_label = QLabel("No image loaded")
        self.file_label.setObjectName("mutedLabel")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        view_row = QHBoxLayout()
        fit_button = QPushButton("Fit scan")
        fit_button.clicked.connect(self.viewer.fit_image)
        fit_card_button = QPushButton("Fit card")
        fit_card_button.setToolTip("Zoom to the cyan outer-card guides without cropping the image")
        fit_card_button.clicked.connect(self.viewer.fit_card_guides)
        actual_button = QPushButton("100%")
        actual_button.clicked.connect(self.viewer.actual_size)
        view_row.addWidget(fit_button)
        view_row.addWidget(fit_card_button)
        view_row.addWidget(actual_button)
        layout.addLayout(view_row)
        self.image_only_controls.extend((fit_button, fit_card_button, actual_button))

        straighten_box = QGroupBox("Straighten scan first")
        straighten_layout = QVBoxLayout(straighten_box)
        straighten_help = QLabel(
            "Click two far-apart points along any straight card edge. The scan rotates at "
            "1:1 scale on a larger canvas, so nothing is cropped."
        )
        straighten_help.setWordWrap(True)
        straighten_layout.addWidget(straighten_help)
        self.straighten_button = QPushButton("Pick 2 points on a card edge")
        self.straighten_button.clicked.connect(self._toggle_straighten_selection)
        straighten_layout.addWidget(self.straighten_button)
        rotation_row = QHBoxLayout()
        rotation_row.addWidget(QLabel("Correction"))
        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-180.0, 180.0)
        self.rotation_spin.setDecimals(2)
        self.rotation_spin.setSingleStep(0.05)
        self.rotation_spin.setSuffix("°")
        self.rotation_spin.setKeyboardTracking(False)
        self.rotation_spin.valueChanged.connect(self._rotation_changed)
        reset_rotation = QPushButton("Reset")
        reset_rotation.clicked.connect(lambda: self.rotation_spin.setValue(0.0))
        rotation_row.addWidget(self.rotation_spin, 1)
        rotation_row.addWidget(reset_rotation)
        straighten_layout.addLayout(rotation_row)
        self.rotation_status = QLabel("Load a scan to straighten it.")
        self.rotation_status.setObjectName("mutedLabel")
        self.rotation_status.setWordWrap(True)
        straighten_layout.addWidget(self.rotation_status)
        layout.addWidget(straighten_box)
        self.image_only_controls.extend(
            (self.straighten_button, self.rotation_spin, reset_rotation)
        )

        hint = QLabel(
            "After straightening, drag cyan card-edge and amber print-edge guides. "
            "Select a guide and use "
            "arrow keys for 1 px, Shift for 0.1 px, or Ctrl for 10 px. Mouse wheel zooms; "
            "drag the background to pan."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        layout.addWidget(hint)

        guides_box = QGroupBox("Guide coordinates")
        grid = QGridLayout(guides_box)
        for row, name in enumerate(GUIDE_ORDER):
            marker = QLabel("●")
            marker.setStyleSheet(
                "color: #15d1c5;" if name.startswith("outer_") else "color: #ffb347;"
            )
            spin = QDoubleSpinBox()
            spin.setDecimals(1)
            spin.setSingleStep(0.1)
            spin.setSuffix(" px")
            spin.setKeyboardTracking(True)
            spin.valueChanged.connect(lambda value, key=name: self.viewer.set_guide_position(key, value))
            self.spinboxes[name] = spin
            grid.addWidget(marker, row, 0)
            grid.addWidget(QLabel(DISPLAY_NAMES[name]), row, 1)
            grid.addWidget(spin, row, 2)
        results_box = QGroupBox("Centering result")
        results_layout = QVBoxLayout(results_box)
        self.overall_assessment = QLabel("Assessment appears after loading")
        self.overall_assessment.setWordWrap(True)
        self.lr_ratio = QLabel("—")
        self.lr_ratio.setObjectName("ratioLabel")
        self.lr_assessment = QLabel("—")
        self.tb_ratio = QLabel("—")
        self.tb_ratio.setObjectName("ratioLabel")
        self.tb_assessment = QLabel("—")
        self.lr_detail = QLabel("Left/right measurements appear here")
        self.tb_detail = QLabel("Top/bottom measurements appear here")
        self.lr_detail.setWordWrap(True)
        self.tb_detail.setWordWrap(True)
        results_layout.addWidget(self.overall_assessment)
        results_layout.addSpacing(5)
        results_layout.addWidget(QLabel("LEFT / RIGHT"))
        results_layout.addWidget(self.lr_ratio)
        results_layout.addWidget(self.lr_assessment)
        results_layout.addWidget(self.lr_detail)
        results_layout.addSpacing(8)
        results_layout.addWidget(QLabel("TOP / BOTTOM"))
        results_layout.addWidget(self.tb_ratio)
        results_layout.addWidget(self.tb_assessment)
        results_layout.addWidget(self.tb_detail)
        layout.addWidget(results_box)

        legend_box = QGroupBox("Plain-English legend")
        legend_layout = QVBoxLayout(legend_box)
        legend_intro = QLabel(
            "50/50 means the opposing borders are equal. The larger number identifies the "
            "wider border. These bands describe geometry only—not a card grade."
        )
        legend_intro.setWordWrap(True)
        legend_layout.addWidget(legend_intro)
        legend = QLabel(
            "<span style='color:#147d64'>●</span> <b>50.0–52.0</b> Very even<br>"
            "<span style='color:#5f7f28'>●</span> <b>52.1–55.0</b> Slight offset<br>"
            "<span style='color:#b66a00'>●</span> <b>55.1–60.0</b> Noticeable offset<br>"
            "<span style='color:#c34a18'>●</span> <b>60.1–65.0</b> Strong offset<br>"
            "<span style='color:#b42318'>●</span> <b>Over 65.0</b> Heavy offset"
        )
        legend.setTextFormat(Qt.TextFormat.RichText)
        legend_layout.addWidget(legend)
        layout.addWidget(legend_box)
        layout.addWidget(guides_box)

        self.dpi_label = QLabel("DPI: —")
        self.dpi_label.setObjectName("mutedLabel")
        layout.addWidget(self.dpi_label)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(contents)
        scroll.setMinimumWidth(350)
        scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        return scroll

    def _set_controls_enabled(self, enabled: bool) -> None:
        for spin in self.spinboxes.values():
            spin.setEnabled(enabled)
        for control in self.image_only_controls:
            control.setEnabled(enabled)

    def choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {self.side_name} scan",
            "",
            "PNG images (*.png);;All images (*.png *.jpg *.jpeg *.tif *.tiff)",
        )
        if path:
            self.load_image(path)

    def load_image(self, path: str | Path) -> bool:
        try:
            loaded = load_scan(path)
        except ImageLoadError as exc:
            QMessageBox.critical(self, "Could not open image", str(exc))
            return False

        self.original_loaded = loaded
        self.rotation_degrees = 0.0
        blocker = QSignalBlocker(self.rotation_spin)
        self.rotation_spin.setValue(0.0)
        del blocker
        self._display_loaded(loaded)
        self._set_controls_enabled(True)
        self.rotation_status.setText(
            "Correction: 0.00°. Straighten before final guide placement; changing rotation resets guides."
        )
        self.imageLoaded.emit()
        return True

    def _display_loaded(
        self,
        loaded: LoadedImage,
        guides: GuidePositions | None = None,
        view_state: tuple[float, QPointF] | None = None,
    ) -> None:
        self.loaded = loaded
        guides = guides or suggested_manual_guides(
            loaded.metadata.width, loaded.metadata.height
        )
        self._configure_spinboxes(guides)
        self.viewer.set_loaded_image(loaded, guides, fit_image=view_state is None)
        if view_state is not None:
            self.viewer.restore_view_state(*view_state)
        original = self.original_loaded or loaded
        working_size = ""
        if abs(self.rotation_degrees) >= 0.005:
            working_size = f" • working canvas {loaded.metadata.width:,} × {loaded.metadata.height:,} px"
        self.file_label.setText(
            f"{loaded.metadata.path.name}\noriginal {original.metadata.width:,} × "
            f"{original.metadata.height:,} px{working_size}"
        )
        self.file_label.setToolTip(str(loaded.metadata.path))
        if loaded.metadata.dpi_x and loaded.metadata.dpi_y:
            self.dpi_label.setText(
                f"DPI metadata: {loaded.metadata.dpi_x:.2f} × {loaded.metadata.dpi_y:.2f}"
            )
        else:
            self.dpi_label.setText("DPI metadata: unavailable — ratios still use pixels")
        self._update_results()

    def _rotation_changed(self, value: float) -> None:
        if self.original_loaded is None:
            return
        previous_angle = self.rotation_degrees
        next_angle = float(value)
        previous_guides = self.guides()
        previous_scale, previous_center = self.viewer.view_state()
        mapped_guides = transform_guides_between_rotations(
            self.original_loaded,
            previous_guides,
            previous_angle,
            next_angle,
        )
        mapped_center_x, mapped_center_y = map_point_between_rotations(
            self.original_loaded,
            (previous_center.x(), previous_center.y()),
            previous_angle,
            next_angle,
        )
        self.rotation_degrees = next_angle
        self.viewer.cancel_straighten_selection()
        self._display_loaded(
            rotate_scan(self.original_loaded, self.rotation_degrees),
            mapped_guides,
            (previous_scale, QPointF(mapped_center_x, mapped_center_y)),
        )
        self.rotation_status.setText(
            f"Correction: {self.rotation_degrees:+.2f}°. Full scan retained at 1:1 scale. "
            "Guides, zoom, and viewing position were retained; fine-tune the guides if needed."
        )

    def _toggle_straighten_selection(self) -> None:
        if self.viewer.in_straighten_mode:
            self.viewer.cancel_straighten_selection()
        else:
            self.viewer.begin_straighten_selection()

    def _straighten_point_count_changed(self, count: int) -> None:
        if self.viewer.in_straighten_mode:
            self.straighten_button.setText(
                "Now click the second point…" if count == 1 else "Click the first point…"
            )
            self.rotation_status.setText(
                "Use two far-apart points on the same physical card edge. Press Esc to cancel."
            )
        else:
            self.straighten_button.setText("Pick 2 points on a card edge")

    def _straighten_from_line(self, first: QPointF, second: QPointF) -> None:
        dx = second.x() - first.x()
        dy = second.y() - first.y()
        if math.hypot(dx, dy) < 5.0:
            QMessageBox.information(
                self,
                "Points too close",
                "Choose two points farther apart on the same card edge for a more accurate angle.",
            )
            return
        correction = straightening_correction(dx, dy)
        new_angle = self.rotation_degrees + correction
        while new_angle > 180.0:
            new_angle -= 360.0
        while new_angle < -180.0:
            new_angle += 360.0
        rounded_angle = round(new_angle, 2)
        if abs(rounded_angle - self.rotation_spin.value()) < 0.005:
            self.rotation_status.setText(
                f"Selected edge is already straight within 0.01° (current correction "
                f"{self.rotation_degrees:+.2f}°)."
            )
        else:
            self.rotation_spin.setValue(rounded_angle)

    def _configure_spinboxes(self, guides: GuidePositions) -> None:
        values = guides.as_dict()
        for name, spin in self.spinboxes.items():
            blocker = QSignalBlocker(spin)
            maximum = self.loaded.metadata.width if "left" in name or "right" in name else self.loaded.metadata.height
            spin.setRange(0.0, float(maximum))
            spin.setValue(values[name])
            del blocker

    def _guide_moved(self, name: str, value: float) -> None:
        spin = self.spinboxes[name]
        blocker = QSignalBlocker(spin)
        spin.setValue(value)
        del blocker

    def guides(self) -> GuidePositions:
        return self.viewer.guides()

    def measurement(self) -> SideMeasurement:
        if self.loaded is None:
            raise RuntimeError(f"No {self.side_name.lower()} image is loaded")
        return calculate_measurement(
            self.guides(), self.loaded.metadata.dpi_x, self.loaded.metadata.dpi_y
        )

    def _update_results(self) -> None:
        if self.loaded is None or not self.viewer.has_image:
            return
        try:
            result = self.measurement()
        except InvalidGuidesError as exc:
            self.lr_ratio.setText("Invalid guides")
            self.tb_ratio.setText("Invalid guides")
            self.lr_detail.setText(str(exc))
            self.tb_detail.clear()
            return

        horizontal = result.horizontal
        vertical = result.vertical
        horizontal_assessment = assess_axis(horizontal)
        vertical_assessment = assess_axis(vertical)
        overall = max(
            (horizontal_assessment, vertical_assessment),
            key=lambda assessment: assessment.larger_side_percent,
        )
        self.overall_assessment.setText(
            f"Overall: {overall.label} — worst border balance is "
            f"{100.0 - overall.larger_side_percent:.1f}/{overall.larger_side_percent:.1f}"
        )
        self.overall_assessment.setStyleSheet(_assessment_style(overall))
        self.lr_ratio.setText(horizontal.ratio_text)
        self.lr_assessment.setText(
            f"{horizontal_assessment.label} • "
            f"{horizontal_assessment.deviation_points:.1f} points from 50/50"
        )
        self.lr_assessment.setStyleSheet(_assessment_style(horizontal_assessment))
        self.lr_detail.setText(
            _distance_text("Left", horizontal.first_px, horizontal.first_mm)
            + "\n"
            + _distance_text("Right", horizontal.second_px, horizontal.second_mm)
            + "\n"
            + _direction_text(horizontal.first_px, horizontal.second_px, "horizontal")
        )
        self.tb_ratio.setText(vertical.ratio_text)
        self.tb_assessment.setText(
            f"{vertical_assessment.label} • "
            f"{vertical_assessment.deviation_points:.1f} points from 50/50"
        )
        self.tb_assessment.setStyleSheet(_assessment_style(vertical_assessment))
        self.tb_detail.setText(
            _distance_text("Top", vertical.first_px, vertical.first_mm)
            + "\n"
            + _distance_text("Bottom", vertical.second_px, vertical.second_mm)
            + "\n"
            + _direction_text(vertical.first_px, vertical.second_px, "vertical")
        )
        self.measurementChanged.emit()

