from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QStandardPaths
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


STYLE = """
QWidget {
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget { background: #f5f6f8; color: #1c2430; }
QFrame#headerFrame, QGroupBox {
    background: #ffffff;
    border: 1px solid #d9dde5;
    border-radius: 7px;
}
QFrame#headerFrame { border-left: 4px solid #2264d1; }
QGroupBox {
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QLabel#titleLabel { font-size: 18pt; font-weight: 700; color: #152238; }
QLabel#mutedLabel { color: #667085; }
QLabel#hintLabel {
    color: #475467;
    background: #eef4ff;
    border: 1px solid #d4e2ff;
    border-radius: 5px;
    padding: 8px;
}
QLabel#ratioLabel { font-size: 22pt; font-weight: 700; color: #174ea6; }
QLineEdit, QDoubleSpinBox {
    background: white;
    border: 1px solid #cfd5df;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QDoubleSpinBox:focus { border: 2px solid #2264d1; }
QPushButton {
    background: #ffffff;
    border: 1px solid #cbd2dc;
    border-radius: 5px;
    padding: 7px 11px;
}
QPushButton:hover { background: #edf2fa; }
QPushButton:pressed { background: #dde7f5; }
QPushButton#primaryButton {
    background: #2264d1;
    color: white;
    border-color: #1d57b6;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #1d57b6; }
QPushButton#primaryButton:disabled { background: #aebbd1; border-color: #aebbd1; }
QTabWidget::pane { border: 1px solid #d9dde5; background: white; }
QTabBar::tab { padding: 9px 24px; background: #e9ecf1; }
QTabBar::tab:selected { background: white; color: #174ea6; font-weight: 600; }
QTableWidget { background: white; alternate-background-color: #f7f9fc; gridline-color: #e4e7ec; }
QHeaderView::section { background: #eef1f5; padding: 6px; border: 0; border-right: 1px solid #d9dde5; font-weight: 600; }
QStatusBar { background: #202a38; color: white; }
"""


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure trading-card scan centering")
    parser.add_argument("--database", type=Path, help="Override the SQLite database path")
    parser.add_argument("--front", type=Path, help="Open a front image on launch")
    parser.add_argument("--back", type=Path, help="Open a back image on launch")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(list(sys.argv[1:] if argv is None else argv))
    QCoreApplication.setOrganizationName("CardCenteringStudio")
    QCoreApplication.setApplicationName("Card Centering Studio")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)

    database_path = args.database
    if database_path is None:
        data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
        database_path = data_dir / "measurements.sqlite3"

    window = MainWindow(database_path)
    if args.front:
        window.front_editor.load_image(args.front)
    if args.back:
        window.back_editor.load_image(args.back)
    window.show()
    return app.exec()

