"""Smoke tests for the installed package."""

import unittest
from importlib.metadata import metadata, version

import ingestra


class PackageTests(unittest.TestCase):
    """Verify the Ingestra import namespace and distribution metadata."""

    def test_package_is_importable(self) -> None:
        """Expose the package under its new import name."""
        self.assertEqual(ingestra.__name__, "ingestra")

    def test_distribution_name_is_ingestra(self) -> None:
        """Publish metadata under the same name as the Python package."""
        self.assertEqual(metadata("ingestra")["Name"], "ingestra")

    def test_given_default_install_when_reading_metadata_then_tiktoken_is_required(self) -> None:
        """Include tiktoken without an optional-extra marker."""
        requirements = metadata("ingestra").get_all("Requires-Dist", [])
        self.assertRegex("\n".join(requirements), r"(?m)^tiktoken[<>=!~][^;\n]*$")

    def test_version_matches_distribution_metadata(self) -> None:
        """Keep the runtime version aligned with the installed distribution."""
        self.assertEqual(ingestra.__version__, version("ingestra"))


if __name__ == "__main__":
    unittest.main()
