from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.gui.settings_store import GuiSettings
from src.gui.tracker_item_create_dialog import TrackerItemCreateRequest
from src.gui.tracker_item_editor import TrackerItemEditorService
from src.gui.tracker_item_editor import TrackerItemFieldChange
from src.gui.tracker_query_models import TrackerItemDetail
from src.gui.tracker_query_models import TrackerItemSummary
from src.gui.tracker_query_service import TrackerQueryService
from src.gui.tracker_workspace import CHILDREN_LOADED_ROLE
from src.gui.tracker_workspace import ITEM_SUMMARY_ROLE
from src.gui.tracker_workspace import TrackerWorkspacePage


SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "gui-offline-sample"


class CountingTrackerQueryService(TrackerQueryService):
    def __init__(self) -> None:
        super().__init__()
        self.child_load_count = 0

    def load_all_child_items(self, *args, **kwargs):
        self.child_load_count += 1
        return super().load_all_child_items(*args, **kwargs)


EDITOR_SCHEMA = {
    "id": 20,
    "fields": [
        {
            "id": 3,
            "name": "Summary",
            "type": "TextField",
            "valueModel": "TextFieldValue",
            "trackerItemField": "name",
            "mandatory": True,
        },
        {
            "id": 7,
            "name": "Status",
            "type": "OptionChoiceField",
            "valueModel": "ChoiceFieldValue<ChoiceOptionReference>",
            "trackerItemField": "status",
            "options": [
                {"id": 1, "name": "Open", "type": "ChoiceOptionReference"},
                {"id": 2, "name": "Review", "type": "ChoiceOptionReference"},
            ],
        },
    ],
}


class EditableWorkspaceClient:
    item = {}
    created_item = None
    calls: list[tuple] = []
    deleted = False

    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs

    @classmethod
    def reset(cls) -> None:
        cls.item = {
            "id": 1001,
            "name": "Original summary",
            "description": "Editable detail",
            "descriptionFormat": "PlainText",
            "version": 1,
            "tracker": {"id": 20, "name": "Requirements"},
            "status": {"id": 1, "name": "Open", "type": "ChoiceOptionReference"},
            "assignedTo": [],
            "children": [],
            "customFields": [],
        }
        cls.calls = []
        cls.deleted = False
        cls.created_item = None

    def get_projects(self):
        return [{"id": 10, "name": "Vehicle"}]

    def get_trackers(self, project_id: int):
        return [{"id": 20, "name": "Requirements", "projectId": project_id}]

    def get_tracker(self, tracker_id: int):
        return {
            "id": tracker_id,
            "name": "Requirements",
            "project": {"id": 10, "name": "Vehicle"},
        }

    def get_tracker_schema(self, tracker_id: int):
        del tracker_id
        return deepcopy(EDITOR_SCHEMA)

    def get_tracker_children_page(self, tracker_id: int, *, page: int, page_size: int):
        del tracker_id
        if self.__class__.deleted:
            items = []
        else:
            item = self.__class__.item
            items = [
                {
                    "id": item["id"],
                    "name": item["name"],
                    "status": deepcopy(item["status"]),
                    "version": item["version"],
                    "hasChildren": False,
                }
            ]
        return {
            "page": page,
            "pageSize": page_size,
            "total": len(items),
            "itemRefs": items,
        }

    def get_item(self, item_id: int):
        self.__class__.calls.append(("get", item_id))
        if (
            self.__class__.created_item is not None
            and item_id == self.__class__.created_item["id"]
        ):
            return deepcopy(self.__class__.created_item)
        if self.__class__.deleted:
            raise KeyError(item_id)
        return deepcopy(self.__class__.item)

    def create_item(
        self,
        tracker_id: int,
        payload: dict,
        parent_item_id: int | None = None,
    ):
        self.__class__.calls.append(
            ("create", tracker_id, deepcopy(payload), parent_item_id)
        )
        created_item = {
            "id": 1002,
            "name": payload["name"],
            "description": payload.get("description", ""),
            "descriptionFormat": "PlainText",
            "version": 1,
            "tracker": {"id": tracker_id, "name": "Requirements"},
            "status": {"id": 1, "name": "Open", "type": "ChoiceOptionReference"},
            "assignedTo": [],
            "children": [],
            "customFields": deepcopy(payload.get("customFields", [])),
        }
        if parent_item_id is not None:
            created_item["parent"] = {
                "id": parent_item_id,
                "name": self.__class__.item["name"],
            }
        self.__class__.created_item = created_item
        return {"id": 1002}

    def update_item_fields(self, item_id: int, field_values: list[dict]):
        self.__class__.calls.append(("update", item_id, deepcopy(field_values)))
        for field_value in field_values:
            if field_value["fieldId"] == 3:
                self.__class__.item["name"] = field_value["value"]
            elif field_value["fieldId"] == 7:
                self.__class__.item["status"] = deepcopy(field_value["values"][0])
        self.__class__.item["version"] += 1
        return deepcopy(self.__class__.item)

    def delete_item(self, item_id: int):
        self.__class__.calls.append(("delete", item_id))
        self.__class__.deleted = True
        return {}


class TrackerWorkspacePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.settings = GuiSettings(
            offline_mode=True,
            offline_schema_path=str(SAMPLE_DIR / "offline_schema.json"),
            offline_tracker_configuration_path=str(
                SAMPLE_DIR / "offline_tracker_configuration.json"
            ),
            offline_query_data_path=str(SAMPLE_DIR / "offline_tracker_items.json"),
        )
        self.service = CountingTrackerQueryService()
        self.page = TrackerWorkspacePage(
            settings_provider=lambda: self.settings,
            service=self.service,
            synchronous=True,
        )
        self.page.show()
        self._app.processEvents()

    def tearDown(self) -> None:
        self.page.close()
        self._app.processEvents()

    def test_activation_loads_project_tracker_and_top_level_items(self) -> None:
        self.page.activate()

        self.assertEqual(self.page.project_combo.count(), 1)
        self.assertEqual(self.page.project_combo.currentData(), 246800)
        self.assertEqual(self.page.tracker_combo.count(), 2)
        self.assertEqual(self.page.tracker_combo.currentData(), 24680001)
        self.assertEqual(self.page.item_tree.topLevelItemCount(), 2)
        self.assertEqual(self.page.item_tree.topLevelItem(0).text(0), "9001001")
        self.assertIn("전체 표시", self.page.tree_status_label.text())
        self.assertIn("Offline Requirements", self.page.search_scope_label.text())
        self.assertTrue(self.page.search_button.isEnabled())
        self.assertFalse(self.page.create_item_button.isEnabled())

    def test_unknown_child_metadata_keeps_tree_item_expandable(self) -> None:
        unknown = TrackerItemSummary.from_raw({"id": 1, "name": "Unknown"})
        known_empty = TrackerItemSummary.from_raw(
            {"id": 2, "name": "Empty", "hasChildren": False}
        )

        unknown_item = self.page._tree_item(unknown)
        empty_item = self.page._tree_item(known_empty)

        self.assertFalse(bool(unknown_item.data(0, CHILDREN_LOADED_ROLE)))
        self.assertEqual(unknown_item.childCount(), 1)
        self.assertTrue(bool(empty_item.data(0, CHILDREN_LOADED_ROLE)))
        self.assertEqual(empty_item.childCount(), 0)

    def test_expanding_node_loads_direct_children_once_and_reuses_cache(self) -> None:
        self.page.activate()
        root = self.page.item_tree.topLevelItem(0)

        self.page._on_tree_item_expanded(root)

        self.assertEqual(self.service.child_load_count, 1)
        self.assertEqual(root.childCount(), 2)
        self.assertEqual(root.child(0).text(0), "9001002")
        self.assertEqual(root.child(1).text(0), "9001003")

        self.page._on_tree_item_expanded(root)

        self.assertEqual(self.service.child_load_count, 1)
        steering = root.child(1)
        self.page._on_tree_item_expanded(steering)
        self.assertEqual(self.service.child_load_count, 2)
        self.assertEqual(steering.child(0).text(0), "9001004")

    def test_tree_selection_loads_read_only_detail_and_masked_raw_json(self) -> None:
        self.page.activate()
        root = self.page.item_tree.topLevelItem(0)
        self.page.item_tree.setCurrentItem(root)
        self._app.processEvents()

        self.assertEqual(self.page.detail_title.text(), "Vehicle requirements")
        self.assertEqual(self.page.detail_id_badge.text(), "#9001001")
        self.assertTrue(self.page.detail_refresh_button.isEnabled())
        self.assertIn("Top-level sample requirement", self.page.detail_description.toPlainText())
        self.assertGreaterEqual(self.page.detail_fields_table.rowCount(), 10)
        self.assertIn('"Risk Level"', self.page.detail_raw_json.toPlainText())

    def test_wiki_rendering_requires_explicit_format_or_field_type(self) -> None:
        detail = TrackerItemDetail.from_raw(
            {
                "id": 1200,
                "name": "Wiki detail",
                "description": "%%(color:red)__설명__%%",
                "descriptionFormat": "Wiki",
                "tracker": {"id": 24680001, "name": "Offline Requirements"},
                "customFields": [
                    {
                        "fieldId": 101,
                        "name": "Wiki field",
                        "type": "WikiTextFieldValue",
                        "value": "%%(color:blue)Wiki 값%%",
                    },
                    {
                        "fieldId": 102,
                        "name": "Plain field",
                        "type": "TextFieldValue",
                        "value": "%%(color:blue)원문 유지%%",
                    },
                    {
                        "fieldId": 103,
                        "name": "Steps",
                        "type": "TableFieldValue",
                        "values": [
                            [
                                {
                                    "fieldId": 104,
                                    "name": "Action",
                                    "type": "WikiTextFieldValue",
                                    "value": "%%red 실행%%",
                                }
                            ]
                        ],
                    },
                ],
            }
        )

        self.page._render_detail(detail)

        self.assertTrue(self.page.description_source_toggle.isVisible())
        self.assertEqual(self.page.detail_description.toPlainText(), "설명")
        self.assertIsNotNone(self.page.detail_fields_table.cellWidget(9, 1))
        self.assertIsNone(self.page.detail_fields_table.cellWidget(10, 1))
        self.assertEqual(
            self.page.detail_fields_table.item(10, 1).text(),
            "%%(color:blue)원문 유지%%",
        )
        self.assertIsNotNone(self.page.detail_fields_table.cellWidget(11, 1))

        self.page.description_source_toggle.setChecked(True)
        self.assertEqual(
            self.page.detail_description.toPlainText(),
            "%%(color:red)__설명__%%",
        )

    def test_plain_description_keeps_wiki_like_text_unchanged(self) -> None:
        detail = TrackerItemDetail.from_raw(
            {
                "id": 1201,
                "name": "Plain detail",
                "description": "%%(color:red)원문%%",
                "descriptionFormat": "PlainText",
                "tracker": {"id": 24680001, "name": "Offline Requirements"},
            }
        )

        self.page._render_detail(detail)

        self.assertFalse(self.page.description_source_toggle.isVisible())
        self.assertEqual(
            self.page.detail_description.toPlainText(),
            "%%(color:red)원문%%",
        )

    def test_test_mode_editor_loads_schema_but_disables_write_actions(self) -> None:
        self.page.activate()
        self.page.item_tree.setCurrentItem(self.page.item_tree.topLevelItem(0))
        self.page.detail_tabs.setCurrentIndex(self.page.editor_tab_index)
        self._app.processEvents()

        self.assertGreater(self.page.editor_panel.field_table.rowCount(), 0)
        self.assertFalse(self.page.editor_panel.save_button.isEnabled())
        self.assertFalse(self.page.editor_panel.transition_button.isEnabled())
        self.assertFalse(self.page.editor_panel.delete_button.isEnabled())
        self.assertIn("테스트 모드", self.page.editor_panel.editor_status.text())

    def test_tracker_search_is_scoped_to_selected_tracker(self) -> None:
        self.page.activate()
        self.page.browser_tabs.setCurrentIndex(1)
        self.page.search_text_input.setText("Steering")

        self.page._run_search()

        requirement_ids = {
            int(self.page.search_table.item(row, 0).text())
            for row in range(self.page.search_table.rowCount())
        }
        self.assertEqual(requirement_ids, {9001003, 9001004})

        self.page._on_tracker_activated(1)
        self.page.search_text_input.setText("Steering")
        self.page._run_search()

        test_case_ids = {
            int(self.page.search_table.item(row, 0).text())
            for row in range(self.page.search_table.rowCount())
        }
        self.assertEqual(test_case_ids, {9101002})
        self.assertNotIn(9001003, test_case_ids)
        self.assertIn("Offline Test Cases", self.page.search_scope_label.text())

    def test_direct_id_open_resolves_other_tracker_and_builds_ancestor_path(self) -> None:
        self.page.activate()
        self.assertEqual(self.page.tracker_combo.currentData(), 24680001)
        self.page.direct_id_input.setText("9101002")

        self.page._open_direct_item()

        self.assertEqual(self.page.tracker_combo.currentData(), 24680002)
        self.assertEqual(self.page.detail_id_badge.text(), "#9101002")
        self.assertEqual(self.page.detail_title.text(), "Steering response test")
        self.assertEqual(self.page.item_tree.topLevelItemCount(), 1)
        root = self.page.item_tree.topLevelItem(0)
        self.assertEqual(root.text(0), "9101001")
        self.assertEqual(root.childCount(), 1)
        self.assertEqual(root.child(0).text(0), "9101002")
        self.assertIn("ID 직접 접근 경로", self.page.tree_status_label.text())

    def test_search_requires_filter_instead_of_loading_entire_tracker(self) -> None:
        self.page.activate()

        self.page._run_search()

        self.assertEqual(self.page.search_table.rowCount(), 0)
        self.assertIn("하나 이상", self.page.workspace_status_label.text())
        self.assertEqual(self.page.workspace_status_label.property("tone"), "warning")

    def test_unconfigured_workspace_guides_user_to_settings(self) -> None:
        page = TrackerWorkspacePage(
            settings_provider=GuiSettings,
            service=self.service,
            synchronous=True,
        )
        try:
            page.activate()

            self.assertFalse(page.direct_open_button.isEnabled())
            self.assertFalse(page.refresh_context_button.isEnabled())
            self.assertIn("활성 연결", page.workspace_status_label.text())
            self.assertEqual(page.workspace_status_label.property("tone"), "warning")
        finally:
            page.close()

    def test_request_tokens_reject_stale_results(self) -> None:
        first = self.page._next_token("detail")
        second = self.page._next_token("detail")

        self.assertFalse(self.page._is_current_token("detail", first))
        self.assertTrue(self.page._is_current_token("detail", second))

    def test_tree_items_store_normalized_models_not_server_dicts(self) -> None:
        self.page.activate()
        value = self.page.item_tree.topLevelItem(0).data(0, ITEM_SUMMARY_ROLE)

        self.assertEqual(value.item_id, 9001001)
        self.assertEqual(value.tracker_id, 24680001)
        self.assertFalse(isinstance(value, dict))


class TrackerWorkspaceWriteIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        EditableWorkspaceClient.reset()
        self.settings = GuiSettings(
            base_url="https://example.test/cb",
            username="sample",
            password="placeholder",
        )
        query_service = TrackerQueryService(client_factory=EditableWorkspaceClient)
        editor_service = TrackerItemEditorService(
            client_factory=EditableWorkspaceClient,
            query_service=query_service,
        )
        self.activities = []
        self.page = TrackerWorkspacePage(
            settings_provider=lambda: self.settings,
            service=query_service,
            editor_service=editor_service,
            delete_confirmer=lambda detail: detail.item_id == 1001,
            activity_recorder=self.activities.append,
            synchronous=True,
        )
        self.page.show()
        self.page.activate()
        self.page.item_tree.setCurrentItem(self.page.item_tree.topLevelItem(0))
        self._app.processEvents()
        self.page.detail_tabs.setCurrentIndex(self.page.editor_tab_index)
        self._app.processEvents()

    def tearDown(self) -> None:
        self.page.close()
        self._app.processEvents()

    def test_field_update_status_transition_and_delete_refresh_visible_state(self) -> None:
        from PySide6.QtCore import Qt

        summary_row = self.page.editor_panel.rows[3]
        self.page.editor_panel.field_table.item(summary_row.row, 0).setCheckState(
            Qt.CheckState.Checked
        )
        summary_row.widget.setText("Changed summary")
        self.page.editor_panel.save_button.click()

        self.assertEqual(self.page.detail_title.text(), "Changed summary")
        self.assertEqual(self.page.item_tree.topLevelItem(0).text(1), "Changed summary")
        update_calls = [call for call in EditableWorkspaceClient.calls if call[0] == "update"]
        self.assertEqual(update_calls[0][2][0]["fieldId"], 3)

        target_index = self.page.editor_panel.status_combo.findData(2)
        self.page.editor_panel.status_combo.setCurrentIndex(target_index)
        self.page.editor_panel.transition_button.click()

        self.assertEqual(self.page.item_tree.topLevelItem(0).text(2), "Review")
        self.assertEqual(self.page.detail_fields_table.item(3, 1).text(), "Review")

        self.page.editor_panel.delete_button.click()

        self.assertTrue(EditableWorkspaceClient.deleted)
        self.assertEqual(self.page.item_tree.topLevelItemCount(), 0)
        self.assertEqual(self.page.detail_title.text(), "아이템 상세")
        self.assertIn(("delete", 1001), EditableWorkspaceClient.calls)
        self.assertEqual(
            [record.operation.value for record in self.activities],
            ["tracker_update", "status_transition", "tracker_delete"],
        )

    def test_version_conflict_keeps_editor_and_visible_item_unchanged(self) -> None:
        from PySide6.QtCore import Qt

        summary_row = self.page.editor_panel.rows[3]
        self.page.editor_panel.field_table.item(summary_row.row, 0).setCheckState(
            Qt.CheckState.Checked
        )
        summary_row.widget.setText("Should not save")
        EditableWorkspaceClient.item["version"] = 9

        self.page.editor_panel.save_button.click()

        self.assertEqual(self.page.detail_title.text(), "Original summary")
        self.assertEqual(self.page.item_tree.topLevelItem(0).text(1), "Original summary")
        self.assertIn("다른 사용자가", self.page.workspace_status_label.text())
        self.assertFalse(
            any(call[0] == "update" for call in EditableWorkspaceClient.calls)
        )
        self.assertEqual(self.activities[-1].operation.value, "tracker_update")
        self.assertEqual(self.activities[-1].result.value, "failed")

    def test_single_create_adds_selected_child_and_opens_created_detail(self) -> None:
        def create_request(schema, tracker, selected_detail):
            self.assertEqual(tracker.tracker_id, 20)
            self.assertEqual(selected_detail.item_id, 1001)
            summary = next(field for field in schema.fields if field.name == "Summary")
            return TrackerItemCreateRequest(
                changes=(TrackerItemFieldChange(summary, "Created child"),),
                parent_item_id=selected_detail.item_id,
            )

        self.page.create_request_provider = create_request
        self.page.create_item_button.click()
        self._app.processEvents()

        create_call = next(
            call for call in EditableWorkspaceClient.calls if call[0] == "create"
        )
        self.assertEqual(create_call[1], 20)
        self.assertEqual(create_call[2], {"name": "Created child"})
        self.assertEqual(create_call[3], 1001)
        root = self.page.item_tree.topLevelItem(0)
        self.assertEqual(root.childCount(), 1)
        self.assertEqual(root.child(0).text(0), "1002")
        self.assertEqual(self.page.detail_id_badge.text(), "#1002")
        self.assertEqual(self.page.detail_title.text(), "Created child")
        self.assertIn("생성했습니다", self.page.workspace_status_label.text())
        self.assertEqual(self.activities[-1].operation.value, "tracker_create")
        self.assertEqual(self.activities[-1].item_id, 1002)


if __name__ == "__main__":
    unittest.main()
