from __future__ import annotations

import base64
from typing import Any

import requests

from .models import OPTION_CONTAINER_KEYS
from .models import USER_SEARCH_RESULT_KEYS
from .models import UserInfo


class CodebeamerClient:
    def __init__(self, base_url: str, username: str, password: str, logger=None):
        """Codebeamer 서버에 요청할 때 필요한 접속 정보를 보관한다."""
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.logger = logger

    def _session(self) -> requests.Session:
        """인증 헤더가 포함된 새 HTTP 세션을 만든다."""
        session = requests.Session()
        token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        session.headers.update({
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        return session

    def _get(self, path: str, params: dict | None = None) -> Any:
        """GET 요청을 보내고 JSON 응답을 돌려준다."""
        url = f"{self.base_url}{path}"
        with self._session() as s:
            resp = s.get(url, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, json_body: dict | None = None, params: dict | None = None) -> Any:
        """POST 요청을 보내고 JSON 응답을 돌려준다."""
        url = f"{self.base_url}{path}"
        with self._session() as s:
            resp = s.post(url, json=json_body, params=params)
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _extract_user_payloads(data: Any) -> list[dict[str, Any]]:
        """사용자 검색 응답에서 실제 사용자 목록만 골라낸다."""
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in USER_SEARCH_RESULT_KEYS:
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def get_projects(self) -> list[dict]:
        """접근 가능한 프로젝트 목록을 가져온다."""
        return self._get("/v3/projects")

    def get_trackers(self, project_id: int) -> list[dict]:
        """프로젝트 안에 있는 트래커 목록을 가져온다."""
        return self._get(f"/v3/projects/{project_id}/trackers")

    def get_tracker(self, tracker_id: int) -> dict:
        """트래커 한 개의 상세 정보를 가져온다."""
        return self._get(f"/v3/trackers/{tracker_id}")

    def get_tracker_items(self, tracker_id: int) -> list[dict]:
        """트래커에 속한 아이템 참조 목록을 가져온다."""
        return self._get(f"/v3/trackers/{tracker_id}/items").get("itemRefs", [])

    def get_tracker_children(self, tracker_id: int) -> list[dict]:
        """트래커 루트 아래에 있는 자식 아이템 목록을 가져온다."""
        return self._get(f"/v3/trackers/{tracker_id}/children").get("itemRefs", [])

    def get_tracker_schema(self, tracker_id: int) -> dict:
        """트래커 스키마를 가져와 필드 구조를 분석할 수 있게 한다."""
        return self._get(f"/v3/trackers/{tracker_id}/schema")

    def get_project_members(self, project_id: int) -> Any:
        """프로젝트 멤버 목록을 가져온다."""
        return self._get(f"/v3/projects/{project_id}/members")

    def get_user_groups(self) -> Any:
        """전체 사용자 그룹 목록을 가져온다."""
        return self._get("/v3/users/groups")

    def get_tracker_field_permissions(self, tracker_id: int, field_id: int) -> Any:
        """특정 field의 permission matrix를 가져온다."""
        return self._get(f"/v3/trackers/{tracker_id}/fields/{field_id}/permissions")

    def get_field_options(self, item_id: int, field_id: int) -> list[dict]:
        """특정 아이템 필드에서 선택 가능한 옵션 목록을 가져온다."""
        data = self._get(f"/v3/items/{item_id}/fields/{field_id}/options")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in OPTION_CONTAINER_KEYS:
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []

    def get_item(self, item_id: int) -> dict:
        """아이템 한 개의 상세 정보를 가져온다."""
        return self._get(f"/v3/items/{item_id}")

    def get_user(self, user_id: int) -> UserInfo:
        """사용자 ID로 사용자 상세 정보를 가져온다."""
        return UserInfo.from_raw(self._get(f"/v3/users/{user_id}"))

    def get_user_by_name(self, name: str) -> UserInfo:
        """이름으로 사용자를 바로 한 건 조회한다."""
        return UserInfo.from_raw(self._get("/v3/users/findByName", params={"name": name}))

    def get_user_by_email(self, email: str) -> UserInfo:
        """이메일 주소로 사용자를 바로 한 건 조회한다."""
        return UserInfo.from_raw(self._get("/v3/users/findByEmail", params={"email": email}))

    def search_users(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        user_status: str | None = None,
        project_id: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> dict:
        """조건에 맞는 사용자 검색 결과를 원본 JSON 형태로 돌려준다."""
        params = {
            "page": page,
            "pageSize": min(page_size, 500),
        }
        body = {
            "name": name,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "userStatus": user_status,
            "projectId": project_id,
        }
        body = {key: value for key, value in body.items() if value not in (None, "")}
        return self._post("/v3/users/search", json_body=body, params=params)

    def search_user_infos(
        self,
        *,
        name: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        user_status: str | None = None,
        project_id: int | None = None,
        page: int = 1,
        page_size: int = 100,
    ) -> list[UserInfo]:
        """사용자 검색 결과를 `UserInfo` 객체 목록으로 변환해 돌려준다."""
        data = self.search_users(
            name=name,
            email=email,
            first_name=first_name,
            last_name=last_name,
            user_status=user_status,
            project_id=project_id,
            page=page,
            page_size=page_size,
        )
        return [UserInfo.from_raw(item) for item in self._extract_user_payloads(data)]

    def create_item(self, tracker_id: int, payload: dict, parent_item_id: int | None = None) -> dict:
        """트래커에 새 아이템을 만들고 서버 응답을 돌려준다."""
        params = {}
        if parent_item_id is not None:
            params["parentItemId"] = parent_item_id
        return self._post(f"/v3/trackers/{tracker_id}/items", json_body=payload, params=params)
