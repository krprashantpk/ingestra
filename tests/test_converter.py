"""Tests for the provider-independent converter interface."""

import inspect
import unittest
from typing import get_type_hints

from ingestra.converter import BaseConverter
from ingestra.converter.base import BaseConverter as ModuleBaseConverter


class StubConverter(BaseConverter):
    async def convert(self, data: bytes) -> tuple[str, dict[str, object]]:
        return "# Converted", {"source": data, "byte_length": len(data)}


class ConverterInterfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_package_exports_the_base_class(self) -> None:
        self.assertIs(BaseConverter, ModuleBaseConverter)

    def test_base_class_cannot_be_instantiated(self) -> None:
        self.assertTrue(inspect.isabstract(BaseConverter))
        with self.assertRaises(TypeError):
            BaseConverter()

    def test_subclass_must_implement_convert(self) -> None:
        class IncompleteConverter(BaseConverter):
            pass

        with self.assertRaises(TypeError):
            IncompleteConverter()

    def test_convert_is_async_and_has_the_shared_type_contract(self) -> None:
        self.assertTrue(inspect.iscoroutinefunction(BaseConverter.convert))
        self.assertEqual(
            get_type_hints(BaseConverter.convert),
            {"data": bytes, "return": tuple[str, dict[str, object]]},
        )

    async def test_custom_converter_can_be_used_through_the_interface(self) -> None:
        converter: BaseConverter = StubConverter()
        data = b"\x00\xffbinary"

        result = await converter.convert(data)

        self.assertIsInstance(result, tuple)
        markdown, metadata = result
        self.assertIsInstance(markdown, str)
        self.assertIsInstance(metadata, dict)
        self.assertEqual(markdown, "# Converted")
        self.assertEqual(metadata, {"source": data, "byte_length": len(data)})

    async def test_empty_bytes_can_be_passed_to_an_implementation(self) -> None:
        converter: BaseConverter = StubConverter()

        self.assertEqual(
            await converter.convert(b""),
            ("# Converted", {"source": b"", "byte_length": 0}),
        )


if __name__ == "__main__":
    unittest.main()
