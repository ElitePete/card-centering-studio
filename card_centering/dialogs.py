from __future__ import annotations

from pathlib import Path
from typing import Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _ratio(row: Mapping[str, object], side: str, axis: str) -> str:
    first, second = ("left", "right") if axis == "lr" else ("top", "bottom")
    return (
        f"{float(row[f'{side}_{axis}_{first}_percent']):.1f}/"
        f"{float(row[f'{side}_{axis}_{second}_percent']):.1f}"
    )


def _axis_deviation(row: Mapping[str, object], side: str, axis: str) -> float:
    first = "left" if axis == "lr" else "top"
    return abs(float(row[f"{side}_{axis}_{first}_percent"]) - 50.0)


def _worst_deviation(row: Mapping[str, object]) -> float:
    return max(
        _axis_deviation(row, side, axis)
        for side in ("front", "back")
        for axis in ("lr", "tb")
    )


class ReportPreviewDialog(QDialog):
    def __init__(
        self,
        report_png: bytes,
        suggested_path: str | Path,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.report_png = report_png
        self.suggested_path = Path(suggested_path)
        self.setWindowTitle("Saved centering report")
        self.resize(1200, 820)

        pixmap = QPixmap()
        if not pixmap.loadFromData(report_png, "PNG"):
            raise ValueError("The stored report image could not be read")
        image_label = QLabel()
        image_label.setPixmap(pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scroll = QScrollArea()
        scroll.setWidget(image_label)
        scroll.setWidgetResizable(False)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        save_button = QPushButton("Save PNG as…")
        save_button.clicked.connect(self._save_as)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        footer = QHBoxLayout()
        footer.addWidget(save_button)
        footer.addStretch(1)
        footer.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addLayout(footer)

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save stored report",
            str(self.suggested_path),
            "PNG image (*.png)",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".png":
            destination = destination.with_suffix(".png")
        try:
            destination.write_bytes(self.report_png)
        except OSError as exc:
            QMessageBox.warning(self, "Could not save report", str(exc))
            return
        QMessageBox.information(self, "Report saved", f"Saved to:\n{destination.resolve()}")


class ComparisonDialog(QDialog):
    def __init__(
        self,
        first: Mapping[str, object],
        second: Mapping[str, object],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Compare saved copies")
        self.resize(820, 520)
        first_name = str(first["card_name"])
        second_name = str(second["card_name"])

        heading = QLabel("Saved-copy centering comparison")
        heading.setObjectName("dialogTitle")
        explanation = QLabel(
            "Lower deviation from 50/50 is more evenly centered. This compares measured "
            "geometry only and is not a grading prediction."
        )
        explanation.setWordWrap(True)

        table = QTableWidget(5, 3)
        table.setHorizontalHeaderLabels(("Metric", first_name, second_name))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        metrics = (
            ("Front left / right", "front", "lr"),
            ("Front top / bottom", "front", "tb"),
            ("Back left / right", "back", "lr"),
            ("Back top / bottom", "back", "tb"),
        )
        for row_index, (label, side, axis) in enumerate(metrics):
            table.setItem(row_index, 0, QTableWidgetItem(label))
            first_item = QTableWidgetItem(_ratio(first, side, axis))
            second_item = QTableWidgetItem(_ratio(second, side, axis))
            first_dev = _axis_deviation(first, side, axis)
            second_dev = _axis_deviation(second, side, axis)
            if abs(first_dev - second_dev) >= 0.05:
                better = first_item if first_dev < second_dev else second_item
                better.setBackground(QColor("#d8f3e8"))
                better.setForeground(QColor("#135c45"))
            table.setItem(row_index, 1, first_item)
            table.setItem(row_index, 2, second_item)

        first_worst = _worst_deviation(first)
        second_worst = _worst_deviation(second)
        table.setItem(4, 0, QTableWidgetItem("Worst-axis deviation"))
        table.setItem(4, 1, QTableWidgetItem(f"{first_worst:.1f} points"))
        table.setItem(4, 2, QTableWidgetItem(f"{second_worst:.1f} points"))
        table.horizontalHeader().setStretchLastSection(True)
        table.resizeColumnsToContents()

        if abs(first_worst - second_worst) < 0.05:
            verdict_text = (
                "Result: These copies are effectively tied by worst-axis deviation "
                f"({first_worst:.1f} points from 50/50)."
            )
        elif first_worst < second_worst:
            verdict_text = (
                f"Result: {first_name} is more evenly centered overall. Its worst axis is "
                f"{first_worst:.1f} points from 50/50 versus {second_worst:.1f}."
            )
        else:
            verdict_text = (
                f"Result: {second_name} is more evenly centered overall. Its worst axis is "
                f"{second_worst:.1f} points from 50/50 versus {first_worst:.1f}."
            )
        verdict = QLabel(verdict_text)
        verdict.setObjectName("comparisonVerdict")
        verdict.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(explanation)
        layout.addWidget(table, 1)
        layout.addWidget(verdict)
        layout.addWidget(buttons)
