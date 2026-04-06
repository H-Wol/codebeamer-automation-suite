from __future__ import annotations

import base64
from typing import Any

import requests


class CodebeamerClient:
    def __init__(self, base_url: str, username: str, password: str, logger=None):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.logger = logger

    def _session(self) -> requests.Session:
        session = requests.Session()
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        session.headers.update({
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        return session

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        with self._session() as s:
            resp = s.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        with self._session() as s:
            resp = s.post(url, json=json_body, params=params)
            resp.raise_for_status()
            return resp.json()

    def get_projects(self) -> list[dict]:
        return self._get("/v3/projects")

    def get_trackers(self, project_id: int) -> list[dict]:
        return self._get(f"/v3/projects/{project_id}/trackers")

    def get_tracker(self, tracker_id: int) -> dict:
        return self._get(f"/v3/trackers/{tracker_id}")

    def get_tracker_children(self, tracker_id: int) -> list[dict]:
        return self._get(f"/v3/trackers/{tracker_id}/children").get("itemRefs", [])

    def get_tracker_schema(self, tracker_id: int) -> dict:
        return self._get(f"/v3/trackers/{tracker_id}/schema")

    def get_field_options(self, item_id: int, field_id: int) -> list[dict]:
        data = self._get(f"/v3/items/{item_id}/fields/{field_id}/options")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("items", "options", "references", "values"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    def get_item(self, item_id: int) -> dict:
        return self._get(f"/v3/items/{item_id}")

    def create_item(self, tracker_id: int, payload: dict, parent_item_id: int | None = None) -> dict:
        params = {}
        if parent_item_id is not None:
            params["parentItemId"] = parent_item_id
        return self._post(f"/v3/trackers/{tracker_id}/items", json_body=payload, params=params)
