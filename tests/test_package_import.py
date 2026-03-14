import importlib
import sys
import unittest


class PackageImportTests(unittest.TestCase):
    def tearDown(self) -> None:
        sys.modules.pop("streamdiffusion", None)
        sys.modules.pop("streamdiffusion.pipeline", None)

    def test_package_import_does_not_eagerly_import_pipeline(self) -> None:
        sys.modules.pop("streamdiffusion", None)
        sys.modules.pop("streamdiffusion.pipeline", None)

        importlib.import_module("streamdiffusion")

        self.assertNotIn("streamdiffusion.pipeline", sys.modules)


if __name__ == "__main__":
    unittest.main()
