import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication, QLabel

from card_centering.dialogs import ComparisonDialog
from card_centering.main_window import MainWindow


class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_front_back_load_and_save_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            front_path = root / "front.png"
            back_path = root / "back.png"
            Image.new("RGB", (500, 700), "white").save(front_path, dpi=(600, 600))
            Image.new("RGB", (500, 700), "#eeeeee").save(back_path, dpi=(600, 600))

            window = MainWindow(root / "test.sqlite3")
            self.assertFalse(window.windowIcon().isNull())
            self.assertTrue(window.front_editor.load_image(front_path))
            self.assertTrue(window.back_editor.load_image(back_path))
            window.card_name.setText("Smoke Test Card")
            front_viewer = window.front_editor.viewer
            for name, value in (
                ("inner_left", 90),
                ("outer_left", 50),
                ("inner_right", 410),
                ("outer_right", 450),
                ("inner_top", 100),
                ("outer_top", 60),
                ("inner_bottom", 600),
                ("outer_bottom", 640),
            ):
                front_viewer.set_guide_position(name, value)
            front_viewer.scale(2.0, 2.0)
            scale_before = front_viewer.transform().m11()
            window.front_editor.viewer.begin_straighten_selection()
            self.assertEqual(
                front_viewer.viewport().cursor().shape(), Qt.CursorShape.CrossCursor
            )
            self.assertFalse(front_viewer._straighten_badge.isHidden())
            window.front_editor.viewer._add_straighten_point(QPointF(20, 20))
            self.assertEqual(
                front_viewer.viewport().cursor().shape(), Qt.CursorShape.CrossCursor
            )
            window.front_editor.viewer._add_straighten_point(QPointF(420, 30))

            self.assertEqual(window.front_editor.measurement().horizontal.ratio_text, "50.0/50.0")
            self.assertAlmostEqual(front_viewer.transform().m11(), scale_before)
            self.assertGreater(front_viewer.guides().outer_left, 40)
            self.assertTrue(front_viewer._straighten_badge.isHidden())
            self.assertTrue(window.save_button.isEnabled())
            self.assertTrue(window.export_button.isEnabled())
            window.save_measurement()
            rows = list(window.database.recent())
            stored_report = window.database.report_png(int(rows[0]["id"]))
            self.assertIsNotNone(stored_report)
            self.assertEqual(window.history.columnCount(), 10)
            self.assertIsNotNone(window.history.cellWidget(0, 9))
            window._clear_canvas()
            self.assertIsNone(window.front_editor.loaded)
            self.assertIsNone(window.back_editor.loaded)
            self.assertEqual(window.card_name.text(), "")
            window.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["card_name"], "Smoke Test Card")
        self.assertEqual(rows[0]["front_rotation_degrees"], 1.43)
        self.assertAlmostEqual(rows[0]["front_lr_left_percent"], 50.0)
        self.assertAlmostEqual(rows[0]["back_tb_top_percent"], 50.0)

    def test_saved_copy_comparison_identifies_lower_worst_deviation(self):
        first = {
            "card_name": "Copy A",
            "front_lr_left_percent": 40.0,
            "front_lr_right_percent": 60.0,
            "front_tb_top_percent": 48.0,
            "front_tb_bottom_percent": 52.0,
            "back_lr_left_percent": 46.0,
            "back_lr_right_percent": 54.0,
            "back_tb_top_percent": 45.0,
            "back_tb_bottom_percent": 55.0,
        }
        second = {
            "card_name": "Copy B",
            "front_lr_left_percent": 49.0,
            "front_lr_right_percent": 51.0,
            "front_tb_top_percent": 48.0,
            "front_tb_bottom_percent": 52.0,
            "back_lr_left_percent": 49.5,
            "back_lr_right_percent": 50.5,
            "back_tb_top_percent": 49.0,
            "back_tb_bottom_percent": 51.0,
        }
        dialog = ComparisonDialog(first, second)
        verdict = dialog.findChild(QLabel, "comparisonVerdict")

        self.assertIsNotNone(verdict)
        self.assertIn("Copy B is more evenly centered", verdict.text())
        dialog.close()


if __name__ == "__main__":
    unittest.main()

