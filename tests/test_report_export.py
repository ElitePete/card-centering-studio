import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from card_centering.image_processing import LoadedImage
from card_centering.measurement import calculate_measurement
from card_centering.models import GuidePositions, ImageMetadata
from card_centering.report_export import ReportSide, export_comparison_report


class ReportExportTests(unittest.TestCase):
    @staticmethod
    def _side(label: str, color: tuple[int, int, int, int]) -> ReportSide:
        width, height = 500, 700
        pixels = np.empty((height, width, 4), dtype=np.uint8)
        pixels[:, :] = color
        metadata = ImageMetadata(
            path=Path(f"{label.lower()}.png"),
            width=width,
            height=height,
            dpi_x=600,
            dpi_y=600,
        )
        image = LoadedImage(pixels, metadata)
        guides = GuidePositions(
            outer_left=45,
            inner_left=85,
            inner_right=410,
            outer_right=455,
            outer_top=55,
            inner_top=100,
            inner_bottom=600,
            outer_bottom=650,
        )
        return ReportSide(
            label=label,
            image=image,
            guides=guides,
            measurement=calculate_measurement(guides, 600, 600),
            rotation_degrees=1.25 if label == "Front" else -0.4,
        )

    def test_exports_side_by_side_png_with_both_guide_colors(self):
        with tempfile.TemporaryDirectory() as directory:
            requested = Path(directory) / "comparison"
            exported = export_comparison_report(
                requested,
                "Test Card — Copy 2",
                self._side("Front", (240, 230, 220, 255)),
                self._side("Back", (210, 220, 235, 255)),
            )

            self.assertEqual(exported.suffix, ".png")
            self.assertTrue(exported.exists())
            with Image.open(exported) as image:
                self.assertEqual(image.format, "PNG")
                self.assertGreater(image.width, image.height)
                pixels = np.asarray(image.convert("RGB"))

            self.assertTrue(np.any(np.all(pixels == (21, 209, 197), axis=2)))
            self.assertTrue(np.any(np.all(pixels == (255, 159, 26), axis=2)))


if __name__ == "__main__":
    unittest.main()
