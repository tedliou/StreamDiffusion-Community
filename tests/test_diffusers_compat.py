import unittest

from streamdiffusion.diffusers_compat import (
    AutoencoderTinyOutput,
    DecoderOutput,
    UNet2DConditionOutput,
)


class DiffusersCompatibilityTests(unittest.TestCase):
    def test_expected_output_classes_are_available_through_compat_module(self) -> None:
        self.assertEqual(AutoencoderTinyOutput.__name__, "AutoencoderTinyOutput")
        self.assertEqual(UNet2DConditionOutput.__name__, "UNet2DConditionOutput")
        self.assertEqual(DecoderOutput.__name__, "DecoderOutput")


if __name__ == "__main__":
    unittest.main()
