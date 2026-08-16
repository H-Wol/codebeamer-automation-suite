from __future__ import annotations

import unittest

from src.codebeamer_client import CodebeamerClient


class RecordingEditorClient(CodebeamerClient):
    def __init__(self) -> None:
        super().__init__("https://example.test/cb", "sample", "placeholder")
        self.put_calls: list[tuple[str, object, object]] = []
        self.delete_calls: list[str] = []

    def _put(self, path: str, json_body: dict | None = None, params=None):
        self.put_calls.append((path, json_body, params))
        return {"id": 1001, "version": 2}

    def _delete(self, path: str, params=None):
        del params
        self.delete_calls.append(path)
        return {}


class CodebeamerClientTrackerEditorTest(unittest.TestCase):
    def test_partial_field_update_uses_fields_endpoint_and_field_values_wrapper(self) -> None:
        client = RecordingEditorClient()
        field_values = [
            {
                "fieldId": 3,
                "name": "Summary",
                "type": "TextFieldValue",
                "value": "Changed",
            }
        ]

        result = client.update_item_fields(1001, field_values)

        self.assertEqual(result["version"], 2)
        self.assertEqual(
            client.put_calls,
            [
                (
                    "/v3/items/1001/fields",
                    {"fieldValues": field_values},
                    None,
                )
            ],
        )

    def test_delete_item_uses_single_item_endpoint(self) -> None:
        client = RecordingEditorClient()

        result = client.delete_item(1001)

        self.assertEqual(result, {})
        self.assertEqual(client.delete_calls, ["/v3/items/1001"])

    def test_bulk_field_update_uses_native_endpoint_and_atomic_query(self) -> None:
        client = RecordingEditorClient()
        operations = [{"itemId": 1001, "fieldValues": [{"fieldId": 3}]}]

        client.bulk_update_item_fields(operations, atomic=False)

        self.assertEqual(
            client.put_calls,
            [("/v3/items/fields", operations, {"atomic": "false"})],
        )


if __name__ == "__main__":
    unittest.main()
