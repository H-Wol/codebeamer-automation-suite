from __future__ import annotations

import unittest

from src.gui.settings_store import GuiSettings
from src.gui.tracker_baseline_compare import BaselineComparisonKind
from src.gui.tracker_baseline_compare import BaselineComparisonSource
from src.gui.tracker_baseline_compare import compare_tracker_items
from src.gui.tracker_query_models import TrackerItemSummary
from src.gui.tracker_query_models import TrackerQuery
from src.gui.tracker_query_service import TrackerQueryService
from src.gui.service_core import OfflineGuiClient


def _summary(item_id: int, *, status: str = "Open", rows=None) -> TrackerItemSummary:
    raw = {
        "id": item_id,
        "name": f"Item {item_id}",
        "status": {"id": status, "name": status, "type": "ChoiceOptionReference"},
        "customFields": [
            {
                "fieldId": 10,
                "name": "Table",
                "type": "TableFieldValue",
                "value": rows if rows is not None else [["A", "1"]],
            }
        ],
    }
    return TrackerItemSummary.from_raw(raw, tracker_id=20)


class _ComparisonClient:
    def __init__(self, *args, **kwargs):
        del args, kwargs

    def get_tracker_baselines(self, tracker_id):
        self.tracker_id = tracker_id
        return [{"id": 11, "name": "R1", "createdAt": "2026-01-01T00:00:00Z"}]

    def get_tracker_items_page(self, tracker_id, *, page, page_size):
        del tracker_id, page_size
        refs = [{"id": item_id, "name": f"Item {item_id}"} for item_id in (1, 2, 3)]
        start = (page - 1) * 2
        return {"page": page, "pageSize": 2, "total": len(refs), "itemRefs": refs[start : start + 2]}

    def get_tracker_items(self, tracker_id):
        return self.get_tracker_items_page(tracker_id, page=1, page_size=500)["itemRefs"]

    def get_item(self, item_id, baseline_id=None):
        items = {
            None: {1: _summary(1).raw_reference, 2: _summary(2).raw_reference},
            11: {1: _summary(1, status="Draft").raw_reference, 3: _summary(3).raw_reference},
        }[baseline_id]
        if item_id not in items:
            raise KeyError(item_id)
        return items[item_id]


class TrackerBaselineComparisonTest(unittest.TestCase):
    def test_offline_client_uses_baseline_snapshot(self):
        query_data = {
            "version": 1,
            "projects": [{"id": 1, "name": "Project"}],
            "trackers": [{"id": 20, "name": "Tracker", "projectId": 1}],
            "items": [{"id": 1, "name": "Current", "trackerId": 20, "customFields": []}],
            "baselines": [{
                "id": 11,
                "name": "R1",
                "trackerId": 20,
                "items": [{"id": 1, "name": "Baseline", "customFields": []}],
            }],
        }
        client = OfflineGuiClient(schema={}, schema_path="sample.json", query_data=query_data)
        self.assertEqual(client.get_tracker_baselines(20)[0]["id"], 11)
        result = client.search_items(
            query_string="tracker.id = 20 ORDER BY item.id ASC",
            baseline_id=11,
        )
        self.assertEqual(result["items"][0]["name"], "Baseline")

    def test_table_field_row_order_is_a_change(self):
        result = compare_tracker_items(
            (_summary(1, rows=[["A", "1"], ["B", "2"]]),),
            (_summary(1, rows=[["B", "2"], ["A", "1"]]),),
            before_source=BaselineComparisonSource(11),
            after_source=BaselineComparisonSource(None),
        )
        self.assertEqual(result.items[0].kind, BaselineComparisonKind.CHANGED)
        self.assertEqual(result.items[0].fields[0].label, "Table")

    def test_comparison_classifies_added_removed_and_changed(self):
        result = compare_tracker_items(
            (_summary(1, status="Draft"), _summary(2)),
            (_summary(1), _summary(3)),
            before_source=BaselineComparisonSource(11),
            after_source=BaselineComparisonSource(None),
        )
        self.assertEqual([item.kind for item in result.items], [
            BaselineComparisonKind.CHANGED,
            BaselineComparisonKind.REMOVED,
            BaselineComparisonKind.ADDED,
        ])

    def test_service_lists_baselines_and_collects_all_pages_for_both_sources(self):
        settings = GuiSettings(base_url="https://example.invalid", username="sample", password="sample")
        service = TrackerQueryService(client_factory=_ComparisonClient)
        baselines = service.load_tracker_baselines(settings, 20)
        self.assertEqual([(baseline.baseline_id, baseline.name) for baseline in baselines], [(11, "R1")])
        result = service.compare_tracker_items_at_sources(
            settings,
            TrackerQuery(tracker_id=20, text="Item"),
            before_source=BaselineComparisonSource(11),
            after_source=BaselineComparisonSource(None),
        )
        self.assertEqual(result.count(BaselineComparisonKind.ADDED), 1)
        self.assertEqual(result.count(BaselineComparisonKind.REMOVED), 1)
        self.assertEqual(result.count(BaselineComparisonKind.CHANGED), 1)

    def test_baseline_list_accepts_tracker_baselines_container(self):
        items = TrackerQueryService._extract_baselines(
            {"data": {"trackerBaselines": [{"id": 11, "name": "R1"}]}}
        )
        self.assertEqual(items, [{"id": 11, "name": "R1"}])

    def test_baseline_list_accepts_paged_references_container(self):
        items = TrackerQueryService._extract_baselines(
            {
                "page": 1,
                "pageSize": 100,
                "total": 1,
                "references": [{"id": 11, "name": "R1", "type": "BaselineReference"}],
            }
        )
        self.assertEqual(items[0]["id"], 11)


if __name__ == "__main__":
    unittest.main()
