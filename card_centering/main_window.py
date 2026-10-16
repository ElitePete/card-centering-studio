from __future__ import annotations

from pathlib import Path
import re

from PySide6.QtCore import QPoint, QSettings, QStandardPaths, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .database import MeasurementDatabase
from .dialogs import ComparisonDialog, ReportPreviewDialog
from .measurement import InvalidGuidesError
from .models import MeasurementRecord
from .report_export import (
    ReportSide,
    comparison_report_png_bytes,
    export_comparison_report,
    retitle_report_png,
)
from .side_editor import SideEditor
from .theme import apply_theme


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
        self.history_rows: dict[int, dict[str, object]] = {}
        self.setWindowTitle("Card Centering Studio")
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "card_centering_icon.svg"
        self.setWindowIcon(QIcon(str(icon_path)))
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
        self.export_button = QPushButton("Export report…")
        self.export_button.clicked.connect(self.export_report)
        reset_button = QPushButton("Reset canvas")
        reset_button.clicked.connect(self.reset_canvas)

        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(subtitle, 1, 0, 1, 2)
        layout.addWidget(QLabel("Card ID / name"), 0, 2)
        layout.addWidget(self.card_name, 1, 2, 1, 8)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(front_button)
        actions.addWidget(back_button)
        actions.addWidget(self.export_button)
        actions.addWidget(self.save_button)
        actions.addWidget(reset_button)
        layout.addLayout(actions, 2, 0, 1, 10)
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
        self.compare_button = QPushButton("Compare checked copies")
        self.compare_button.setEnabled(False)
        self.compare_button.clicked.connect(self.compare_checked)
        filter_row.addWidget(self.compare_button)
        layout.addLayout(filter_row)
        self.history = QTableWidget(0, 10)
        self.history.setHorizontalHeaderLabels(
            [
                "Compare",
                "Saved",
                "Card ID / name",
                "Front tilt",
                "Front L/R",
                "Front T/B",
                "Back tilt",
                "Back L/R",
                "Back T/B",
                "Report",
            ]
        )
        self.history.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.history.setAlternatingRowColors(True)
        self.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self._history_context_menu)
        self.history.cellDoubleClicked.connect(self._history_double_clicked)
        self.history.itemChanged.connect(self._history_item_changed)
        self.history.verticalHeader().setVisible(False)
        header = self.history.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.history.setMinimumHeight(150)
        layout.addWidget(self.history)
        return box

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        view_menu = self.menuBar().addMenu("&View")
        help_menu = self.menuBar().addMenu("&Help")

        save_action = QAction("Save measurement", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_measurement)
        export_action = QAction("Export comparison report", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_report)
        reset_action = QAction("Reset canvas", self)
        reset_action.setShortcut(QKeySequence.StandardKey.New)
        reset_action.triggered.connect(self.reset_canvas)
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addActions((save_action, export_action, reset_action))
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        fit_action = QAction("Fit image", self)
        fit_action.setShortcut(QKeySequence("F"))
        fit_action.triggered.connect(self._fit_current)
        view_menu.addAction(fit_action)
        self.dark_mode_action = QAction("Dark mode", self)
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(
            QSettings().value("appearance/dark_mode", False, type=bool)
        )
        self.dark_mode_action.toggled.connect(self._set_dark_mode)
        view_menu.addAction(self.dark_mode_action)

        about_action = QAction("About Card Centering Studio", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def _set_dark_mode(self, enabled: bool) -> None:
        QSettings().setValue("appearance/dark_mode", enabled)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, enabled)

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Card Centering Studio",
            "<h3>Card Centering Studio</h3>"
            f"<p>Version {__version__}</p>"
            "<p>Pixel-accurate trading-card centering measurements.</p>"
            "<p><b>Lambda Core Engineering LLC</b></p>"
            "<p>Released under the MIT License. Geometry only—no grading predictions.</p>",
        )

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

    def reset_canvas(self) -> None:
        has_work = bool(
            self.card_name.text().strip()
            or self.front_editor.loaded
            or self.back_editor.loaded
        )
        if has_work:
            answer = QMessageBox.question(
                self,
                "Reset canvas?",
                "Clear the card name, both imported scans, guides, and current results? "
                "Saved history will not be changed.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._clear_canvas()

    def _clear_canvas(self) -> None:
        self.front_editor.clear_image()
        self.back_editor.clear_image()
        self.card_name.clear()
        self.tabs.setCurrentIndex(0)
        self._state_changed()
        self.statusBar().showMessage("Canvas reset; saved history was left unchanged.", 6000)

    def _state_changed(self) -> None:
        ready = bool(self.card_name.text().strip()) and bool(
            self.front_editor.loaded and self.back_editor.loaded
        )
        self.save_button.setEnabled(ready)
        self.export_button.setEnabled(ready)

    def _report_sides(self, front, back) -> tuple[ReportSide, ReportSide]:
        if self.front_editor.loaded is None or self.back_editor.loaded is None:
            raise RuntimeError("Both scans are required")
        return (
            ReportSide(
                "Front",
                self.front_editor.loaded,
                self.front_editor.guides(),
                front,
                self.front_editor.rotation_degrees,
            ),
            ReportSide(
                "Back",
                self.back_editor.loaded,
                self.back_editor.guides(),
                back,
                self.back_editor.rotation_degrees,
            ),
        )

    def export_report(self) -> None:
        card_name = self.card_name.text().strip()
        if not card_name:
            QMessageBox.information(
                self, "Card ID required", "Enter a card ID or name before exporting."
            )
            self.card_name.setFocus()
            return
        if self.front_editor.loaded is None or self.back_editor.loaded is None:
            QMessageBox.information(
                self,
                "Both scans required",
                "Import both a front scan and a back scan before exporting.",
            )
            return

        try:
            front_measurement = self.front_editor.measurement()
            back_measurement = self.back_editor.measurement()
        except (InvalidGuidesError, RuntimeError) as exc:
            QMessageBox.warning(self, "Cannot export report", str(exc))
            return

        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "", card_name).strip(" .")
        safe_name = safe_name or "card"
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        suggested = str(Path(documents) / f"{safe_name} centering report.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export front and back comparison report",
            suggested,
            "PNG image (*.png)",
        )
        if not path:
            return

        try:
            front_side, back_side = self._report_sides(
                front_measurement, back_measurement
            )
            destination = export_comparison_report(
                path,
                card_name,
                front_side,
                back_side,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not export report", str(exc))
            return

        self.statusBar().showMessage(f"Exported report to {destination}", 9000)
        QMessageBox.information(
            self,
            "Report exported",
            f"The front/back comparison report was saved to:\n{destination}",
        )

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
        try:
            front_side, back_side = self._report_sides(front, back)
            report_png = comparison_report_png_bytes(
                card_name, front_side, back_side
            )
        except (OSError, ValueError, RuntimeError) as exc:
            QMessageBox.warning(
                self,
                "Cannot save measurement",
                f"The saved-copy report could not be created:\n{exc}",
            )
            return
        record_id = self.database.save(record, report_png=report_png)
        self.refresh_history()
        self.statusBar().showMessage(
            f"Saved measurement and report #{record_id} for {card_name}", 7000
        )

    def refresh_history(self) -> None:
        card_filter = self.history_filter.text() if hasattr(self, "history_filter") else ""
        rows = list(self.database.recent(card_filter=card_filter))
        self.history_rows = {int(row["id"]): dict(row) for row in rows}
        self.history.blockSignals(True)
        try:
            self.history.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                record_id = int(row["id"])
                check_item = QTableWidgetItem()
                check_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                )
                check_item.setCheckState(Qt.CheckState.Unchecked)
                check_item.setData(Qt.ItemDataRole.UserRole, record_id)
                check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history.setItem(row_index, 0, check_item)

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
                tooltip = (
                    f"Front: {row['front_path']} ({row['front_rotation_degrees']:+.2f}°)\n"
                    f"Back: {row['back_path']} ({row['back_rotation_degrees']:+.2f}°)"
                )
                for column, value in enumerate(values, start=1):
                    item = QTableWidgetItem(str(value))
                    if column >= 3:
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    item.setToolTip(tooltip)
                    self.history.setItem(row_index, column, item)

                report_button = QPushButton(
                    "View report" if row["has_report"] else "Unavailable"
                )
                report_button.setEnabled(bool(row["has_report"]))
                report_button.clicked.connect(
                    lambda _checked=False, item_id=record_id: self.view_saved_report(
                        item_id
                    )
                )
                self.history.setCellWidget(row_index, 9, report_button)
        finally:
            self.history.blockSignals(False)
        self._update_compare_button()

    def _history_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_compare_button()

    def _checked_history_ids(self) -> list[int]:
        checked: list[int] = []
        for row in range(self.history.rowCount()):
            item = self.history.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                checked.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return checked

    def _update_compare_button(self) -> None:
        if hasattr(self, "compare_button"):
            count = len(self._checked_history_ids())
            self.compare_button.setEnabled(count == 2)
            self.compare_button.setText(
                "Compare checked copies" if count == 0 else f"Compare checked copies ({count}/2)"
            )

    def compare_checked(self) -> None:
        record_ids = self._checked_history_ids()
        if len(record_ids) != 2:
            QMessageBox.information(
                self,
                "Choose two copies",
                "Check exactly two saved copies to compare them.",
            )
            return
        self._show_comparison(record_ids[0], record_ids[1])

    def _show_comparison(self, first_id: int, second_id: int) -> None:
        first = self.history_rows.get(first_id)
        second = self.history_rows.get(second_id)
        if first is None or second is None:
            all_rows = {int(row["id"]): dict(row) for row in self.database.recent(limit=500)}
            first = all_rows.get(first_id)
            second = all_rows.get(second_id)
        if first is None or second is None:
            QMessageBox.warning(self, "Cannot compare", "One of the saved copies no longer exists.")
            return
        ComparisonDialog(first, second, self).exec()

    def _history_double_clicked(self, row: int, _column: int) -> None:
        item = self.history.item(row, 0)
        if item is not None:
            self.view_saved_report(int(item.data(Qt.ItemDataRole.UserRole)))

    def _history_context_menu(self, position: QPoint) -> None:
        row = self.history.rowAt(position.y())
        if row < 0:
            return
        item = self.history.item(row, 0)
        if item is None:
            return
        record_id = int(item.data(Qt.ItemDataRole.UserRole))
        record = self.history_rows.get(record_id)
        if record is None:
            return
        menu = QMenu(self)
        view_action = menu.addAction("View report")
        save_action = menu.addAction("Save report as…")
        has_report = bool(record["has_report"])
        view_action.setEnabled(has_report)
        save_action.setEnabled(has_report)
        menu.addSeparator()
        rename_action = menu.addAction("Rename…")
        compare_action = menu.addAction("Compare with another…")
        delete_action = menu.addAction("Delete…")
        chosen = menu.exec(self.history.viewport().mapToGlobal(position))
        if chosen == view_action:
            self.view_saved_report(record_id)
        elif chosen == save_action:
            self.save_saved_report_as(record_id)
        elif chosen == rename_action:
            self.rename_saved_copy(record_id)
        elif chosen == compare_action:
            self.compare_with_another(record_id)
        elif chosen == delete_action:
            self.delete_saved_copy(record_id)

    def _suggested_report_path(self, card_name: str) -> Path:
        safe_name = re.sub(r"[^A-Za-z0-9._ -]+", "", card_name).strip(" .") or "card"
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        return Path(documents) / f"{safe_name} centering report.png"

    def view_saved_report(self, record_id: int) -> None:
        report_png = self.database.report_png(record_id)
        record = self.history_rows.get(record_id)
        if not report_png or record is None:
            QMessageBox.information(
                self,
                "Report unavailable",
                "This older saved copy does not contain an embedded report. New saves include one automatically.",
            )
            return
        try:
            ReportPreviewDialog(
                report_png,
                self._suggested_report_path(str(record["card_name"])),
                self,
            ).exec()
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot open report", str(exc))

    def save_saved_report_as(self, record_id: int) -> None:
        report_png = self.database.report_png(record_id)
        record = self.history_rows.get(record_id)
        if not report_png or record is None:
            QMessageBox.information(self, "Report unavailable", "No report is stored for this copy.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save stored report",
            str(self._suggested_report_path(str(record["card_name"]))),
            "PNG image (*.png)",
        )
        if not path:
            return
        destination = Path(path)
        if destination.suffix.lower() != ".png":
            destination = destination.with_suffix(".png")
        try:
            destination.write_bytes(report_png)
        except OSError as exc:
            QMessageBox.warning(self, "Could not save report", str(exc))
            return
        self.statusBar().showMessage(f"Saved stored report to {destination.resolve()}", 8000)

    def rename_saved_copy(self, record_id: int) -> None:
        record = self.history_rows.get(record_id)
        if record is None:
            return
        current_name = str(record["card_name"])
        name, accepted = QInputDialog.getText(
            self, "Rename saved copy", "Card ID / name", text=current_name
        )
        name = name.strip()
        if not accepted or not name or name == current_name:
            return
        report_png = self.database.report_png(record_id)
        if report_png:
            try:
                report_png = retitle_report_png(report_png, name)
            except (OSError, ValueError):
                report_png = None
        self.database.rename(record_id, name, report_png)
        self.refresh_history()
        self.statusBar().showMessage(f"Renamed saved copy #{record_id} to {name}", 6000)

    def compare_with_another(self, record_id: int) -> None:
        candidates = [
            dict(row)
            for row in self.database.recent(limit=500)
            if int(row["id"]) != record_id
        ]
        if not candidates:
            QMessageBox.information(
                self, "No other copies", "Save another copy before comparing."
            )
            return
        labels = [
            f"#{row['id']}  {row['card_name']}  —  {str(row['created_at']).replace('T', ' ').removesuffix('Z')}"
            for row in candidates
        ]
        label, accepted = QInputDialog.getItem(
            self, "Compare saved copies", "Compare with", labels, 0, False
        )
        if not accepted:
            return
        second = candidates[labels.index(label)]
        self._show_comparison(record_id, int(second["id"]))

    def delete_saved_copy(self, record_id: int) -> None:
        record = self.history_rows.get(record_id)
        if record is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete saved copy?",
            f"Permanently delete #{record_id} — {record['card_name']} and its embedded report?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.database.delete(record_id)
        self.refresh_history()
        self.statusBar().showMessage(f"Deleted saved copy #{record_id}", 6000)

