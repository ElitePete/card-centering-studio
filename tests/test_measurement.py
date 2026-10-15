import unittest

from card_centering.measurement import (
    InvalidGuidesError,
    assess_axis,
    calculate_measurement,
    pixels_to_mm,
)
from card_centering.models import AxisMeasurement, GuidePositions


class MeasurementTests(unittest.TestCase):
    def test_calculates_direct_pixel_ratios(self):
        guides = GuidePositions(
            outer_left=10,
            inner_left=110,
            inner_right=890,
            outer_right=1000,
            outer_top=20,
            inner_top=70,
            inner_bottom=930,
            outer_bottom=980,
        )

        result = calculate_measurement(guides)

        self.assertEqual(result.horizontal.first_px, 100)
        self.assertEqual(result.horizontal.second_px, 110)
        self.assertAlmostEqual(result.horizontal.first_percent, 47.6190476)
        self.assertAlmostEqual(result.horizontal.second_percent, 52.3809524)
        self.assertEqual(result.horizontal.ratio_text, "47.6/52.4")
        self.assertEqual(result.vertical.ratio_text, "50.0/50.0")

    def test_dpi_only_affects_optional_physical_values(self):
        guides = GuidePositions(0, 100, 900, 1000, 0, 60, 940, 1000)

        without_dpi = calculate_measurement(guides)
        with_dpi = calculate_measurement(guides, dpi_x=500, dpi_y=600)

        self.assertEqual(without_dpi.horizontal.ratio_text, with_dpi.horizontal.ratio_text)
        self.assertEqual(without_dpi.vertical.ratio_text, with_dpi.vertical.ratio_text)
        self.assertIsNone(without_dpi.horizontal.first_mm)
        self.assertAlmostEqual(with_dpi.horizontal.first_mm, 5.08)
        self.assertAlmostEqual(with_dpi.vertical.first_mm, 2.54)

    def test_rejects_crossed_guides(self):
        guides = GuidePositions(100, 50, 900, 1000, 0, 50, 950, 1000)
        with self.assertRaises(InvalidGuidesError):
            calculate_measurement(guides)

    def test_rejects_zero_total_border(self):
        guides = GuidePositions(0, 0, 1000, 1000, 0, 50, 950, 1000)
        with self.assertRaises(InvalidGuidesError):
            calculate_measurement(guides)

    def test_invalid_dpi_does_not_create_mm_value(self):
        self.assertIsNone(pixels_to_mm(100, None))
        self.assertIsNone(pixels_to_mm(100, 0))

    def test_plain_language_assessment_bands(self):
        cases = (
            (51.0, "Very even"),
            (54.3, "Slight offset"),
            (58.0, "Noticeable offset"),
            (63.0, "Strong offset"),
            (70.0, "Heavy offset"),
        )
        for larger, expected in cases:
            with self.subTest(larger=larger):
                axis = AxisMeasurement(1, 1, 100 - larger, larger)
                self.assertEqual(assess_axis(axis).label, expected)


if __name__ == "__main__":
    unittest.main()

