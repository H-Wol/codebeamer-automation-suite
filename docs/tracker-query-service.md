# 트래커 조회 서비스 계약

## 현재 상태

이 문서는 `feature/tracker-query-service`에서 구현한 읽기 전용 데이터 계층을 설명합니다.
확장형 트리와 상세 화면은 다음 `feature/tracker-item-browser` 단계에서 이 계약을 사용합니다.

현재 구현된 범위:

- 프로젝트와 트래커 목록 정규화
- 트래커 최상위 아이템과 아이템의 직접 하위 목록 조회
- 간편, 조건 조합, CbQL 검색을 하나의 `TrackerQuery`로 표현
- 선택 tracker ID를 모든 검색 CbQL에 강제로 결합
- 아이템 상세, builtin/custom field, 부모·자식 요약과 원본 JSON 정규화
- ID 직접 접근용 프로젝트·트래커 컨텍스트와 parent 조상 경로 조회
- 서버 pagination 응답과 사용자 요청값의 분리 보존
- 인증, 권한, 없음, 요청 제한, 잘못된 조건, 네트워크, 서버 오류 분류
- credential 계열 키의 원본 JSON 마스킹
- 두 tracker를 포함한 익명 테스트 모드 snapshot

쓰기, 상태 전환, 단건 생성, 관계·댓글·첨부·이력은 이 서비스의 범위가 아닙니다.

## 온라인 API 경계

| 기능 | V3 endpoint | 구현 위치 |
| --- | --- | --- |
| 트래커 아이템 참조 | `GET /v3/trackers/{trackerId}/items` | `CodebeamerClient.get_tracker_items_page()` |
| 트래커 최상위 아이템 | `GET /v3/trackers/{trackerId}/children` | `CodebeamerClient.get_tracker_children_page()` |
| 직접 하위 아이템 | `GET /v3/items/{itemId}/children` | `CodebeamerClient.get_item_children_page()` |
| 조건 검색 | `GET /v3/items/query` | `CodebeamerClient.search_items()` |
| 상세 | `GET /v3/items/{itemId}` | `CodebeamerClient.get_item()` |
| schema | `GET /v3/trackers/{trackerId}/schema` | `CodebeamerClient.get_tracker_schema()` |

PTC 문서의 목록 응답은 `page`, `pageSize`, `total`을 포함하지만, 서버 버전과 endpoint에 따라
요청한 페이지가 실제로 적용되지 않고 전체 결과가 반환될 수 있습니다. `PageResult`는 서버 응답값과
`requested_page`, `requested_page_size`를 함께 저장하고 `server_honored_pagination`을 별도로 제공합니다.
화면은 요청값만 보고 pagination이 지원된다고 가정하면 안 됩니다.

참고:

- [PTC Tracker Item Operations](https://support.ptc.com/help/codebeamer/r3.2/en/codebeamer/developers_guide/swagger/11375769.html)
- [PTC Retrieve Child Tracker Items](https://support.ptc.com/help/codebeamer/r2.2/en/codebeamer/developers_guide/dg_retrieving_list_of_child_tracker_items.html)
- [PTC cbQL Order](https://support.ptc.com/help/codebeamer/r3.2/en/codebeamer/user_guide/ug_cbql_order.html)
- [PTC Pagination](https://support.ptc.com/help/codebeamer/r2.2/en/codebeamer/developers_guide/dg_pagination.html)

## 검색 범위 보장

`TrackerQuery.build_cbql()`은 사용자 조건을 항상 아래 형태로 감쌉니다.

```text
tracker.id = <현재 tracker ID> AND (<사용자 조건>) ORDER BY <검증된 정렬식>
```

- 간편 검색은 ID/요약, 상태, 담당자를 조합합니다.
- 조건 조합은 그룹 내부 AND, 그룹 사이 OR만 지원합니다.
- 빈 조건 조합은 tracker 전체 조회로 바꾸지 않고 실행을 차단합니다.
- CbQL 모드는 조건식과 `ORDER BY`만 받으며 `SELECT`, `GROUP BY`, 다중 문장을 차단합니다.
- 서버가 다른 tracker의 아이템을 반환하면 결과에서 숨기지 않고 서비스 오류로 처리합니다.

## 화면용 모델

- `ProjectSummary`, `TrackerSummary`: 컨텍스트 선택기
- `TrackerQuery`, `TrackerQueryCondition`, `TrackerQueryGroup`: 검색 조건
- `TrackerItemSummary`: 트리와 검색 결과의 최소 표시 데이터
- `TrackerItemDetail`: builtin/custom field, parent/children, 마스킹된 원본 응답
- `TrackerItemContext`: ID 직접 접근으로 확인한 프로젝트·트래커와 상세
- `PageResult`: 서버와 요청 pagination 메타데이터
- `TrackerQueryServiceError`: 사용자 대응이 가능한 오류 분류

Qt widget은 서버 원본 dict를 직접 탐색하지 않고 위 모델만 사용해야 합니다.

## 테스트 모드 조회 snapshot

설정의 `조회 데이터 Snapshot`은 version 1 JSON 객체이며 다음 목록을 포함합니다.

```json
{
  "version": 1,
  "projects": [],
  "trackers": [],
  "items": []
}
```

규칙:

- project, tracker, item ID는 양의 정수이며 각 범위에서 중복될 수 없습니다.
- tracker는 `projectId`, item은 `trackerId`를 반드시 참조합니다.
- `parentId`가 있으면 같은 tracker의 기존 item이어야 합니다.
- snapshot이 없으면 배치 Dry Run은 계속 사용할 수 있지만 트래커 작업공간 조회는 명시적으로 차단합니다.
- 테스트 모드 CbQL evaluator가 해석하지 못하는 표현식은 결과를 가장하지 않고 `invalid_query`로 처리합니다.

기본 fixture는 `data/gui-offline-sample/offline_tracker_items.json`입니다.

## 다음 화면 단계의 사용 원칙

- 최상위 목록은 `load_top_level_items()`로 한 번만 요청합니다.
- 노드를 펼칠 때 `load_child_items()`를 호출하고 화면 세션에서 결과를 캐시합니다.
- 행 선택은 `load_detail()`을 별도 비동기 요청으로 실행합니다.
- ID 바로 열기는 `resolve_item_context()` 후 `load_ancestor_path()`를 사용합니다.
- 늦게 끝난 요청이 현재 선택을 덮지 않도록 화면 controller가 request token을 비교합니다.
