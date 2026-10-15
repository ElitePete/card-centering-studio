import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QApplication

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
            window.front_editor.viewer._add_straighten_point(QPointF(420, 30))

            self.assertEqual(window.front_editor.measurement().horizontal.ratio_text, "50.0/50.0")
            self.assertAlmostEqual(front_viewer.transform().m11(), scale_before)
            self.assertGreater(front_viewer.guides().outer_left, 40)
            self.assertTrue(front_viewer._straighten_badge.isHidden())
            self.assertTrue(window.save_button.isEnabled())
            self.assertTrue(window.export_button.isEnabled())
            window.save_measurement()
            rows = list(window.database.recent())
            window.close()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["card_name"], "Smoke Test Card")
        self.assertEqual(rows[0]["front_rotation_degrees"], 1.43)
        self.assertAlmostEqual(rows[0]["front_lr_left_percent"], 50.0)
        self.assertAlmostEqual(rows[0]["back_tb_top_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()

