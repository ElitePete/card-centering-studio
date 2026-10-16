from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .theme import apply_theme


def _arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure trading-card scan centering")
    parser.add_argument("--database", type=Path, help="Override the SQLite database path")
    parser.add_argument("--front", type=Path, help="Open a front image on launch")
    parser.add_argument("--back", type=Path, help="Open a back image on launch")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _arguments(list(sys.argv[1:] if argv is None else argv))
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "LambdaCoreEngineering.CardCenteringStudio"
            )
        except (AttributeError, OSError):
            pass
    QCoreApplication.setOrganizationName("CardCenteringStudio")
    QCoreApplication.setApplicationName("Card Centering Studio")
    app = QApplication(sys.argv[:1])
    app.setStyle("Fusion")
    icon_path = Path(__file__).resolve().parent.parent / "assets" / "card_centering_icon.svg"
    app.setWindowIcon(QIcon(str(icon_path)))
    dark_mode = QSettings().value("appearance/dark_mode", False, type=bool)
    apply_theme(app, dark_mode)

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

