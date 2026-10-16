from __future__ import annotations

from PySide6.QtWidgets import QApplication


LIGHT_STYLE = """
QWidget { font-family: "Segoe UI"; font-size: 10pt; }
QMainWindow, QWidget { background: #f5f6f8; color: #1c2430; }
QFrame#headerFrame, QGroupBox { background: #ffffff; border: 1px solid #d9dde5; border-radius: 7px; }
QFrame#headerFrame { border-left: 4px solid #2264d1; }
QGroupBox { margin-top: 10px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QLabel#titleLabel, QLabel#dialogTitle { font-size: 18pt; font-weight: 700; color: #152238; }
QLabel#mutedLabel { color: #667085; }
QLabel#hintLabel { color: #475467; background: #eef4ff; border: 1px solid #d4e2ff; border-radius: 5px; padding: 8px; }
QLabel#ratioLabel { font-size: 22pt; font-weight: 700; color: #174ea6; }
QLabel#comparisonVerdict { background: #eef4ff; border: 1px solid #c9dafe; border-radius: 6px; padding: 12px; font-weight: 600; }
QLineEdit, QDoubleSpinBox { background: white; border: 1px solid #cfd5df; border-radius: 4px; padding: 6px; }
QLineEdit:focus, QDoubleSpinBox:focus { border: 2px solid #2264d1; }
QPushButton { background: #ffffff; border: 1px solid #cbd2dc; border-radius: 5px; padding: 7px 11px; }
QPushButton:hover { background: #edf2fa; }
QPushButton:pressed { background: #dde7f5; }
QPushButton#primaryButton { background: #2264d1; color: white; border-color: #1d57b6; font-weight: 600; }
QPushButton#primaryButton:hover { background: #1d57b6; }
QPushButton#primaryButton:disabled { background: #aebbd1; border-color: #aebbd1; }
QTabWidget::pane { border: 1px solid #d9dde5; background: white; }
QTabBar::tab { padding: 9px 24px; background: #e9ecf1; }
QTabBar::tab:selected { background: white; color: #174ea6; font-weight: 600; }
QTableWidget { background: white; alternate-background-color: #f7f9fc; gridline-color: #e4e7ec; }
QHeaderView::section { background: #eef1f5; padding: 6px; border: 0; border-right: 1px solid #d9dde5; font-weight: 600; }
QMenuBar, QMenu { background: #ffffff; color: #1c2430; }
QMenu::item:selected { background: #dce8fb; }
QStatusBar { background: #202a38; color: white; }
"""


DARK_STYLE = """
QWidget { font-family: "Segoe UI"; font-size: 10pt; }
QMainWindow, QWidget { background: #171a21; color: #e6e9ef; }
QFrame#headerFrame, QGroupBox { background: #20242d; border: 1px solid #3b4250; border-radius: 7px; }
QFrame#headerFrame { border-left: 4px solid #5b91ec; }
QGroupBox { margin-top: 10px; padding-top: 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #e6e9ef; }
QLabel#titleLabel, QLabel#dialogTitle { font-size: 18pt; font-weight: 700; color: #f4f7fb; }
QLabel#mutedLabel { color: #aab3c2; }
QLabel#hintLabel { color: #c7d5ed; background: #242f42; border: 1px solid #3c5376; border-radius: 5px; padding: 8px; }
QLabel#ratioLabel { font-size: 22pt; font-weight: 700; color: #82adff; }
QLabel#comparisonVerdict { background: #242f42; border: 1px solid #3c5376; border-radius: 6px; padding: 12px; font-weight: 600; }
QLineEdit, QDoubleSpinBox { background: #151820; color: #edf0f5; border: 1px solid #4a5262; border-radius: 4px; padding: 6px; selection-background-color: #3569b8; }
QLineEdit:focus, QDoubleSpinBox:focus { border: 2px solid #669cf2; }
QPushButton { background: #2a2f3a; color: #edf0f5; border: 1px solid #4a5262; border-radius: 5px; padding: 7px 11px; }
QPushButton:hover { background: #353c49; }
QPushButton:pressed { background: #424b5b; }
QPushButton:disabled { color: #77808f; background: #242832; }
QPushButton#primaryButton { background: #356fd0; color: white; border-color: #4f88e5; font-weight: 600; }
QPushButton#primaryButton:hover { background: #477fdd; }
QPushButton#primaryButton:disabled { background: #34445e; border-color: #34445e; color: #8d99aa; }
QTabWidget::pane { border: 1px solid #3b4250; background: #20242d; }
QTabBar::tab { padding: 9px 24px; background: #292e38; color: #b9c0cb; }
QTabBar::tab:selected { background: #20242d; color: #82adff; font-weight: 600; }
QTableWidget { background: #1d2129; color: #e6e9ef; alternate-background-color: #242933; gridline-color: #343b48; selection-background-color: #315d9d; }
QTableWidget QTableCornerButton::section, QHeaderView::section { background: #2a303b; color: #edf0f5; padding: 6px; border: 0; border-right: 1px solid #424a58; font-weight: 600; }
QScrollArea { border-color: #3b4250; }
QMenuBar, QMenu { background: #20242d; color: #e6e9ef; }
QMenu::item:selected { background: #315d9d; }
QToolTip { color: #f4f7fb; background: #252a34; border: 1px solid #586273; }
QStatusBar { background: #0f1117; color: #e6e9ef; }
"""


def apply_theme(app: QApplication, dark: bool) -> None:
    app.setStyleSheet(DARK_STYLE if dark else LIGHT_STYLE)
