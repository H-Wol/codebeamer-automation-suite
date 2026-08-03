from __future__ import annotations

import unittest

from src.codebeamer_client import CodebeamerClient


class RecordingCodebeamerClient(CodebeamerClient):
    def __init__(self) -> None:
        super().__init__("https://example.test/cb", "sample", "placeholder")
        self.get_calls: list[tuple[str, dict | None]] = []

    def _get(self, path: str, params: dict | None = None):
        self.get_calls.append((path, params))
        return {"page": 1, "pageSize": 25, "total": 0, "itemRefs": []}


class CodebeamerClientTrackerQueryTest(unittest.TestCase):
    def test_tracker_item_page_uses_v3_endpoint_and_clamps_pagination(self) -> None:
        client = RecordingCodebeamerClient()

        result = client.get_tracker_items_page(42, page=0, page_size=999)

        self.assertEqual(result["total"], 0)
        self.assertEqual(
            client.get_calls,
            [("/v3/trackers/42/items", {"page": 1, "pageSize": 500})],
        )

    def test_tracker_root_page_uses_tracker_children_endpoint(self) -> None:
        client = RecordingCodebeamerClient()

        client.get_tracker_children_page(42, page=2, page_size=50)

        self.assertEqual(
            client.get_calls,
            [("/v3/trackers/42/children", {"page": 2, "pageSize": 50})],
        )

    def test_direct_child_page_uses_item_children_endpoint(self) -> None:
        client = RecordingCodebeamerClient()

        client.get_item_children_page(1001, page=3, page_size=20)

        self.assertEqual(
            client.get_calls,
            [("/v3/items/1001/children", {"page": 3, "pageSize": 20})],
        )


if __name__ == "__main__":
    unittest.main()
