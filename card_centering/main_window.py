from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import MeasurementDatabase
from .measurement import InvalidGuidesError
from .models import MeasurementRecord
from .side_editor import SideEditor


def _ratio(row, side: str, axis: str) -> str:
    first, second = ("left", "right") if axis == "lr" else ("top", "bottom")
    return (
        f"{row[f'{side}_{axis}_{first}_percent']:.1f}/"
        f"{row[f'{side}_{axis}_{second}_percent']:.1f}"
    )


class MainWindow(QMainWindow):
    def __init__(self, database_path: str | Path, parent=None):
        super().__init__(parent)
        self.database = MeasurementDatabase(database_path)
        self.setWindowTitle("Card Centering Studio")
        self.resize(1480, 940)
        self.setMinimumSize(1050, 720)

        self.front_editor = SideEditor("Front")
        self.back_editor = SideEditor("Back")
        self.tabs = QTabWidget()
        self.tabs.addTab(self.front_editor, "Front scan")
        self.tabs.addTab(self.back_editor, "Back scan")

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)
        root_layout.addWidget(self._build_header())

        vertical_splitter = QSplitter(Qt.Orientation.Vertical)
        vertical_splitter.addWidget(self.tabs)
        vertical_splitter.addWidget(self._build_history())
        vertical_splitter.setStretchFactor(0, 1)
        vertical_splitter.setStretchFactor(1, 0)
        vertical_splitter.setSizes([720, 190])
        root_layout.addWidget(vertical_splitter, 1)
        self.setCentralWidget(root)

        self._build_actions()
        self.statusBar().showMessage(f"Database: {self.database.path}")
        self.front_editor.imageLoaded.connect(self._state_changed)
        self.back_editor.imageLoaded.connect(self._state_changed)
        self.card_name.textChanged.connect(self._state_changed)
        self._state_changed()
        self.refresh_history()

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("headerFrame")
        layout = QGridLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)

        title = QLabel("Card Centering Studio")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Manual, pixel-accurate front and back centering measurements")
        subtitle.setObjectName("mutedLabel")
        self.card_name = QLineEdit()
        self.card_name.setPlaceholderText("e.g. 1999 Base Set Charizard #4 — Copy 2")
        self.card_name.setClearButtonEnabled(True)

        front_button = QPushButton("Import front PNG…")
        front_button.clicked.connect(lambda: self._choose_for(self.front_editor, 0))
        back_button = QPushButton("Import back PNG…")
        back_button.clicked.connect(lambda: self._choose_for(self.back_editor, 1))
        self.save_button = QPushButton("Save measurement")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_measurement)

        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(subtitle, 1, 0, 1, 2)
        layout.addWidget(QLabel("Card ID / name"), 0, 2)
        layout.addWidget(self.card_name, 1, 2, 1, 3)
        layout.addWidget(front_button, 0, 5, 2, 1)
        layout.addWidget(back_button, 0, 6, 2, 1)
        layout.addWidget(self.save_button, 0, 7, 2, 1)
        layout.setColumnStretch(2, 1)
        return frame

    def _build_history(self) -> QWidget:
        box = QGroupBox("Saved copies — compare measurements")
        layout = QVBoxLayout(box)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter"))
        self.history_filter = QLineEdit()
        self.history_filter.setPlaceholderText("Find a card ID or name in the saved history")
        self.history_filter.setClearButtonEnabled(True)
        self.history_filter.textChanged.connect(lambda: self.refresh_history())
        filter_row.addWidget(self.history_filter, 1)
        layout.addLayout(filter_row)
        self.history = QTableWidget(0, 8)
        self.history.setHorizontalHeaderLabels(
            [
                "Saved",
                "Card ID / name",
                "Front tilt",
                "Front L/R",
                "Front T/B",
                "Back tilt",
                "Back L/R",
                "Back T/B",
            ]
        )
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setAlternatingRowColors(True)
        self.history.verticalHeader().setVisible(False)
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.history.setMinimumHeight(150)
        layout.addWidget(self.history)
        return box

    def _build_actions(self) -> None:
        save_action = QAction("Save measurement", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_measurement)
        self.addAction(save_action)

        fit_action = QAction("Fit image", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(self._fit_current)
        self.addAction(fit_action)

    def _fit_current(self) -> None:
        editor = self.front_editor if self.tabs.currentIndex() == 0 else self.back_editor
        editor.viewer.fit_image()

    def _choose_for(self, editor: SideEditor, tab_index: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import {editor.side_name.lower()} scan",
            "",
            "PNG images (*.png);;All images (*.png *.jpg *.jpeg *.tif *.tiff)",
        )
        if path and editor.load_image(path):
            self.tabs.setCurrentIndex(tab_index)

    def _state_changed(self) -> None:
        ready = bool(self.card_name.text().strip()) and bool(
            self.front_editor.loaded and self.back_editor.loaded
        )
        self.save_button.setEnabled(ready)

    def save_measurement(self) -> None:
        card_name = self.card_name.text().strip()
        if not card_name:
            QMessageBox.information(self, "Card ID required", "Enter a card ID or name before saving.")
            self.card_name.setFocus()
            return
        if self.front_editor.loaded is None or self.back_editor.loaded is None:
            QMessageBox.information(
                self,
                "Both scans required",
                "Import both a front scan and a back scan before saving.",
            )
            return

        try:
            front = self.front_editor.measurement()
            back = self.back_editor.measurement()
        except (InvalidGuidesError, RuntimeError) as exc:
            QMessageBox.warning(self, "Cannot save measurement", str(exc))
            return

        front_metadata = self.front_editor.loaded.metadata
        back_metadata = self.back_editor.loaded.metadata
        record = MeasurementRecord(
            card_name=card_name,
            front_path=str(front_metadata.path),
            back_path=str(back_metadata.path),
            front=front,
            back=back,
            front_dpi_x=front_metadata.dpi_x,
            front_dpi_y=front_metadata.dpi_y,
            back_dpi_x=back_metadata.dpi_x,
            back_dpi_y=back_metadata.dpi_y,
            front_rotation_degrees=self.front_editor.rotation_degrees,
            back_rotation_degrees=self.back_editor.rotation_degrees,
        )
        record_id = self.database.save(record)
        self.refresh_history()
        self.statusBar().showMessage(
            f"Saved measurement #{record_id} for {card_name}", 7000
        )

    def refresh_history(self) -> None:
        card_filter = self.history_filter.text() if hasattr(self, "history_filter") else ""
        rows = list(self.database.recent(card_filter=card_filter))
        self.history.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            saved = row["created_at"].replace("T", " ").removesuffix("Z")
            values = (
                saved,
                row["card_name"],
                f"{row['front_rotation_degrees']:+.2f}°",
                _ratio(row, "front", "lr"),
                _ratio(row, "front", "tb"),
                f"{row['back_rotation_degrees']:+.2f}°",
                _ratio(row, "back", "lr"),
                _ratio(row, "back", "tb"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(
                    f"Front: {row['front_path']} ({row['front_rotation_degrees']:+.2f}°)\n"
                    f"Back: {row['back_path']} ({row['back_rotation_degrees']:+.2f}°)"
                )
                self.history.setItem(row_index, column, item)

