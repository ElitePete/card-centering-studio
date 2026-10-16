import tempfile
import unittest
import sqlite3
from contextlib import closing
from pathlib import Path

from card_centering.database import MeasurementDatabase, SCHEMA
from card_centering.models import AxisMeasurement, MeasurementRecord, SideMeasurement


class DatabaseTests(unittest.TestCase):
    def test_saves_front_and_back_axes_as_independent_values(self):
        axis_a = AxisMeasurement(98, 102, 49, 51, 4.1, 4.3)
        axis_b = AxisMeasurement(51, 49, 51, 49, 2.2, 2.1)
        axis_a_without_dpi = AxisMeasurement(98, 102, 49, 51)
        axis_b_without_dpi = AxisMeasurement(51, 49, 51, 49)
        record = MeasurementRecord(
            card_name="Test Card — Copy 2",
            front_path="front.png",
            back_path="back.png",
            front=SideMeasurement(axis_a, axis_b),
            back=SideMeasurement(axis_b_without_dpi, axis_a_without_dpi),
            front_dpi_x=600,
            front_dpi_y=600,
            back_dpi_x=None,
            back_dpi_y=None,
        )

        with tempfile.TemporaryDirectory() as directory:
            database = MeasurementDatabase(Path(directory) / "measurements.sqlite3")
            record_id = database.save(record, report_png=b"stored report")
            rows = list(database.recent())
            matching_rows = list(database.recent(card_filter="Copy 2"))
            nonmatching_rows = list(database.recent(card_filter="Different card"))
            stored_report = database.report_png(record_id)
            renamed = database.rename(record_id, "Renamed copy", b"retitled report")
            renamed_rows = list(database.recent())
            renamed_report = database.report_png(record_id)
            deleted = database.delete(record_id)
            remaining_rows = list(database.recent())

        self.assertEqual(record_id, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(matching_rows), 1)
        self.assertEqual(len(nonmatching_rows), 0)
        self.assertEqual(rows[0]["card_name"], "Test Card — Copy 2")
        self.assertEqual(rows[0]["front_left_px"], 98)
        self.assertEqual(rows[0]["front_top_px"], 51)
        self.assertEqual(rows[0]["back_left_px"], 51)
        self.assertEqual(rows[0]["back_top_px"], 98)
        self.assertIsNone(rows[0]["back_left_mm"])
        self.assertEqual(rows[0]["has_report"], 1)
        self.assertEqual(stored_report, b"stored report")
        self.assertTrue(renamed)
        self.assertEqual(renamed_rows[0]["card_name"], "Renamed copy")
        self.assertEqual(renamed_report, b"retitled report")
        self.assertTrue(deleted)
        self.assertEqual(remaining_rows, [])

    def test_adds_rotation_columns_to_existing_v1_database(self):
        old_schema = SCHEMA.replace(
            "    front_rotation_degrees REAL NOT NULL DEFAULT 0,\n"
            "    back_rotation_degrees REAL NOT NULL DEFAULT 0,\n",
            "",
        ).replace(
            "    back_bottom_mm REAL,\n    report_png BLOB\n",
            "    back_bottom_mm REAL\n",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.sqlite3"
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(old_schema)

            database = MeasurementDatabase(path)
            with closing(sqlite3.connect(database.path)) as connection:
                columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(measurements)")
                }

        self.assertIn("front_rotation_degrees", columns)
        self.assertIn("back_rotation_degrees", columns)
        self.assertIn("report_png", columns)


if __name__ == "__main__":
    unittest.main()

