from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable

from .models import MeasurementRecord


MEASUREMENT_COLUMNS = (
    "card_name",
    "front_path",
    "back_path",
    "front_dpi_x",
    "front_dpi_y",
    "back_dpi_x",
    "back_dpi_y",
    "front_rotation_degrees",
    "back_rotation_degrees",
    "front_left_px",
    "front_right_px",
    "front_lr_left_percent",
    "front_lr_right_percent",
    "front_left_mm",
    "front_right_mm",
    "front_top_px",
    "front_bottom_px",
    "front_tb_top_percent",
    "front_tb_bottom_percent",
    "front_top_mm",
    "front_bottom_mm",
    "back_left_px",
    "back_right_px",
    "back_lr_left_percent",
    "back_lr_right_percent",
    "back_left_mm",
    "back_right_mm",
    "back_top_px",
    "back_bottom_px",
    "back_tb_top_percent",
    "back_tb_bottom_percent",
    "back_top_mm",
    "back_bottom_mm",
)


SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    front_path TEXT NOT NULL,
    back_path TEXT NOT NULL,
    front_dpi_x REAL,
    front_dpi_y REAL,
    back_dpi_x REAL,
    back_dpi_y REAL,
    front_rotation_degrees REAL NOT NULL DEFAULT 0,
    back_rotation_degrees REAL NOT NULL DEFAULT 0,
    front_left_px REAL NOT NULL,
    front_right_px REAL NOT NULL,
    front_lr_left_percent REAL NOT NULL,
    front_lr_right_percent REAL NOT NULL,
    front_left_mm REAL,
    front_right_mm REAL,
    front_top_px REAL NOT NULL,
    front_bottom_px REAL NOT NULL,
    front_tb_top_percent REAL NOT NULL,
    front_tb_bottom_percent REAL NOT NULL,
    front_top_mm REAL,
    front_bottom_mm REAL,
    back_left_px REAL NOT NULL,
    back_right_px REAL NOT NULL,
    back_lr_left_percent REAL NOT NULL,
    back_lr_right_percent REAL NOT NULL,
    back_left_mm REAL,
    back_right_mm REAL,
    back_top_px REAL NOT NULL,
    back_bottom_px REAL NOT NULL,
    back_tb_top_percent REAL NOT NULL,
    back_tb_bottom_percent REAL NOT NULL,
    back_top_mm REAL,
    back_bottom_mm REAL
);
CREATE INDEX IF NOT EXISTS idx_measurements_card_name
ON measurements(card_name COLLATE NOCASE);
"""


class MeasurementDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(SCHEMA)
            existing = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(measurements)")
            }
            for column in ("front_rotation_degrees", "back_rotation_degrees"):
                if column not in existing:
                    connection.execute(
                        f"ALTER TABLE measurements ADD COLUMN {column} "
                        "REAL NOT NULL DEFAULT 0"
                    )
            connection.commit()

    def save(self, record: MeasurementRecord) -> int:
        values = record.flat_values()
        columns = ", ".join(MEASUREMENT_COLUMNS)
        placeholders = ", ".join(f":{name}" for name in MEASUREMENT_COLUMNS)
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    f"INSERT INTO measurements ({columns}) VALUES ({placeholders})", values
                )
                return int(cursor.lastrowid)

    def recent(self, limit: int = 100, card_filter: str = "") -> Iterable[sqlite3.Row]:
        with closing(self._connect()) as connection:
            if card_filter.strip():
                query = (
                    "SELECT * FROM measurements WHERE card_name LIKE ? ESCAPE '\\' "
                    "COLLATE NOCASE ORDER BY id DESC LIMIT ?"
                )
                escaped = card_filter.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                parameters = (f"%{escaped}%", limit)
            else:
                query = "SELECT * FROM measurements ORDER BY id DESC LIMIT ?"
                parameters = (limit,)
            return list(
                connection.execute(query, parameters)
            )

