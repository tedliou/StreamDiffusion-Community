import tomllib
import unittest
from pathlib import Path

from packaging.requirements import Requirement


PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def load_project_metadata() -> dict:
    with PYPROJECT_PATH.open("rb") as handle:
        return tomllib.load(handle)["project"]


def requirement_map(requirements: list[str]) -> dict[str, Requirement]:
    return {requirement.name: requirement for requirement in map(Requirement, requirements)}


class ProjectMetadataTests(unittest.TestCase):
    def test_core_and_acceleration_pins_match_supported_baselines(self) -> None:
        project = load_project_metadata()
        dependencies = requirement_map(project["dependencies"])
        tensorrt_dependencies = requirement_map(project["optional-dependencies"]["tensorrt"])

        self.assertEqual(str(dependencies["diffusers"].specifier), "==0.37.0")
        self.assertEqual(str(tensorrt_dependencies["onnx"].specifier), "==1.20.1")
        self.assertEqual(str(tensorrt_dependencies["onnxruntime"].specifier), "==1.24.3")
        self.assertEqual(str(tensorrt_dependencies["protobuf"].specifier), "==7.34.0")

    def test_dev_and_tensorrt_extras_keep_shared_baselines_aligned(self) -> None:
        project = load_project_metadata()
        optional_dependencies = project["optional-dependencies"]
        tensorrt_dependencies = requirement_map(optional_dependencies["tensorrt"])
        dev_dependencies = requirement_map(optional_dependencies["dev"])

        shared_packages = ["colored", "cuda-python", "onnx", "onnxruntime", "protobuf", "pywin32"]

        for package_name in shared_packages:
            self.assertIn(package_name, tensorrt_dependencies)
            self.assertIn(package_name, dev_dependencies)
            self.assertEqual(
                str(tensorrt_dependencies[package_name]),
                str(dev_dependencies[package_name]),
            )


if __name__ == "__main__":
    unittest.main()
