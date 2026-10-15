import tempfile
import unittest
from pathlib import Path

from PIL import Image

from card_centering.image_processing import load_scan, rotate_scan, straightening_correction


class ImageProcessingTests(unittest.TestCase):
    def test_loads_png_pixels_and_dpi_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.png"
            Image.new("RGB", (320, 480), "#b03030").save(path, dpi=(600, 600))

            loaded = load_scan(path)

        self.assertEqual(loaded.metadata.width, 320)
        self.assertEqual(loaded.metadata.height, 480)
        self.assertEqual(loaded.pixels_bgra.shape, (480, 320, 4))
        self.assertAlmostEqual(loaded.metadata.dpi_x, 600, places=1)
        self.assertAlmostEqual(loaded.metadata.dpi_y, 600, places=1)

    def test_rotation_expands_canvas_without_changing_dpi(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.png"
            Image.new("RGB", (320, 480), "white").save(path, dpi=(600, 600))
            loaded = load_scan(path)

            rotated = rotate_scan(loaded, 3.0)

        self.assertGreater(rotated.metadata.width, loaded.metadata.width)
        self.assertGreater(rotated.metadata.height, loaded.metadata.height)
        self.assertEqual(rotated.metadata.dpi_x, loaded.metadata.dpi_x)
        self.assertEqual(rotated.metadata.dpi_y, loaded.metadata.dpi_y)

    def test_two_point_correction_uses_nearest_axis(self):
        two_degrees = 0.0349207695
        self.assertAlmostEqual(straightening_correction(100, 100 * two_degrees), 2.0, places=2)
        self.assertAlmostEqual(straightening_correction(-100, -100 * two_degrees), 2.0, places=2)
        self.assertAlmostEqual(straightening_correction(-100 * two_degrees, 100), 2.0, places=2)


if __name__ == "__main__":
    unittest.main()

