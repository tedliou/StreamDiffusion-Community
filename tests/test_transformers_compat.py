import types
import unittest

from streamdiffusion.compat import resolve_clip_image_processor_class


class TransformersCompatibilityTests(unittest.TestCase):
    def test_prefers_modern_clip_image_processor_when_available(self) -> None:
        legacy = type("LegacyProcessor", (), {})
        modern = type("ModernProcessor", (), {})
        transformers_module = types.SimpleNamespace(
            CLIPFeatureExtractor=legacy,
            CLIPImageProcessor=modern,
        )

        self.assertIs(resolve_clip_image_processor_class(transformers_module), modern)

    def test_falls_back_to_legacy_clip_feature_extractor(self) -> None:
        legacy = type("LegacyProcessor", (), {})
        transformers_module = types.SimpleNamespace(CLIPFeatureExtractor=legacy)

        self.assertIs(resolve_clip_image_processor_class(transformers_module), legacy)

    def test_raises_import_error_when_no_supported_processor_exists(self) -> None:
        with self.assertRaises(ImportError):
            resolve_clip_image_processor_class(types.SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
