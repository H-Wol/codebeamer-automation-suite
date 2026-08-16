from __future__ import annotations

import unittest

from src.codebeamer_client import CodebeamerClient


class RecordingCodebeamerClient(CodebeamerClient):
    def __init__(self) -> None:
        super().__init__("https://example.test/cb", "sample", "placeholder")
        self.get_calls: list[tuple[str, dict | None]] = []
        self.response = {"page": 1, "pageSize": 25, "total": 0, "itemRefs": []}
        self.post_calls: list[tuple[str, dict | None, dict | None]] = []

    def _get(self, path: str, params: dict | None = None):
        self.get_calls.append((path, params))
        return self.response

    def _post(self, path: str, json_body: dict | None = None, params: dict | None = None):
        self.post_calls.append((path, json_body, params))
        return self.response


class PagedBaselineClient(RecordingCodebeamerClient):
    def __init__(self, responses: dict[int, object]) -> None:
        super().__init__()
        self.responses = responses

    def _get(self, path: str, params: dict | None = None):
        self.get_calls.append((path, params))
        page = int((params or {}).get("page", 1))
        return self.responses[page]


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

    def test_tracker_baselines_reads_paged_references(self) -> None:
        client = RecordingCodebeamerClient()
        client.response = {
            "page": 1,
            "pageSize": 1,
            "total": 1,
            "references": [{"id": 7, "name": "R1", "type": "BaselineReference"}],
        }

        result = client.get_tracker_baselines(42)

        self.assertEqual(result, client.response["references"])
        self.assertEqual(
            client.get_calls,
            [("/v3/trackers/42/baselines", {"page": 1, "pageSize": 500})],
        )

    def test_tracker_baselines_collects_all_pages_and_deduplicates_ids(self) -> None:
        client = PagedBaselineClient({
            1: {
                "page": 1,
                "pageSize": 2,
                "total": 3,
                "references": [
                    {"id": 7, "name": "R1", "type": "BaselineReference"},
                    {"id": 8, "name": "R2", "type": "BaselineReference"},
                ],
            },
            2: {
                "page": 2,
                "pageSize": 2,
                "total": 3,
                "references": [
                    {"id": "8", "name": "R2 duplicate", "type": "BaselineReference"},
                    {"id": 9, "name": "R3", "type": "BaselineReference"},
                ],
            },
        })

        result = client.get_tracker_baselines(42)

        self.assertEqual([item["id"] for item in result], [7, 8, 9])
        self.assertEqual(
            client.get_calls,
            [
                ("/v3/trackers/42/baselines", {"page": 1, "pageSize": 500}),
                ("/v3/trackers/42/baselines", {"page": 2, "pageSize": 500}),
            ],
        )

    def test_tracker_baselines_stops_when_server_repeats_same_page(self) -> None:
        repeated = {
            "page": 1,
            "pageSize": 1,
            "total": 2,
            "references": [
                {"id": 7, "name": "R1", "type": "BaselineReference"},
            ],
        }
        client = PagedBaselineClient({1: repeated, 2: repeated})

        with self.assertRaisesRegex(RuntimeError, "다음 페이지를 적용하지 않았습니다"):
            client.get_tracker_baselines(42)

        self.assertEqual(len(client.get_calls), 2)

    def test_tracker_baselines_keeps_legacy_list_response_compatibility(self) -> None:
        client = PagedBaselineClient({
            1: [
                {"id": 7, "name": "R1", "type": "BaselineReference"},
                {"id": 8, "name": "R2", "type": "BaselineReference"},
            ]
        })

        result = client.get_tracker_baselines(42)

        self.assertEqual([item["id"] for item in result], [7, 8])
        self.assertEqual(len(client.get_calls), 1)

    def test_item_detail_adds_baseline_id_to_existing_endpoint(self) -> None:
        client = RecordingCodebeamerClient()

        client.get_item(1001, baseline_id=7)

        self.assertEqual(
            client.get_calls,
            [("/v3/items/1001", {"baselineId": 7})],
        )

    def test_item_context_uses_current_item_read_endpoints(self) -> None:
        client = RecordingCodebeamerClient()

        client.get_item_relations(1001)
        client.get_item_history(1001)

        self.assertEqual(
            client.get_calls,
            [
                ("/v3/items/1001/relations", None),
                ("/v3/items/1001/history", None),
            ],
        )

    def test_wiki_render_uses_project_context_without_baseline_parameter(self) -> None:
        client = RecordingCodebeamerClient()
        client.response = {"html": "<p>완료</p>"}

        result = client.render_wiki_to_html(
            10,
            context_id=1001,
            context_version=7,
            markup="|| 이름 || 상태",
        )

        self.assertEqual(result, "<p>완료</p>")
        self.assertEqual(
            client.post_calls,
            [
                (
                    "/v3/projects/10/wiki2html",
                    {
                        "contextId": 1001,
                        "contextVersion": 7,
                        "markup": "|| 이름 || 상태",
                        "renderingContextType": "TRACKER_ITEM",
                    },
                    None,
                )
            ],
        )

    def test_attachment_metadata_uses_dedicated_v3_path(self) -> None:
        client = RecordingCodebeamerClient()

        client.get_item_attachments(1001)

        self.assertEqual(
            client.get_calls,
            [("/v3/items/1001/attachments", {"page": 1, "pageSize": 500})],
        )

    def test_attachment_metadata_collects_all_pages(self) -> None:
        client = PagedBaselineClient(
            {
                1: {
                    "page": 1,
                    "pageSize": 1,
                    "total": 2,
                    "attachments": [{"id": 28, "name": "one.png"}],
                },
                2: {
                    "page": 2,
                    "pageSize": 1,
                    "total": 2,
                    "attachments": [{"id": 29, "name": "two.txt"}],
                },
            }
        )

        result = client.get_item_attachments(1001)

        self.assertEqual([item["id"] for item in result], [28, 29])
        self.assertEqual(len(client.get_calls), 2)

    def test_comments_use_v3_path_and_collect_all_pages(self) -> None:
        client = PagedBaselineClient(
            {
                1: {"page": 1, "pageSize": 1, "total": 2, "comments": [{"id": 1, "comment": "one"}]},
                2: {"page": 2, "pageSize": 1, "total": 2, "comments": [{"id": "2", "comment": "two"}]},
            }
        )

        result = client.get_item_comments(1001)

        self.assertEqual([item["id"] for item in result], [1, "2"])
        self.assertEqual(
            client.get_calls,
            [
                ("/v3/items/1001/comments", {"page": 1, "pageSize": 500}),
                ("/v3/items/1001/comments", {"page": 2, "pageSize": 500}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
