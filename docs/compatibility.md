# 호환 경로 감사

최종 감사일: 2026-07-29

현재 구현의 단일 출처와 과거 호출 경로가 섞이지 않도록 호환 wrapper의 유지 근거를
정리합니다. 아래 파일에는 새 로직을 추가하지 않습니다.

| 경로 | 저장소 내 사용 | 결정 | 근거와 종료 조건 |
| --- | --- | --- | --- |
| `main.py` | 문서의 과거 CLI 실행 안내 | 유지(비권장) | `cli_main.main`만 다시 노출합니다. 사용자 실행 경로의 완충 역할이 있으므로 다음 major 버전 전까지 유지합니다. |
| `src/excel_processor.py` | offline payload 통합 테스트와 과거 import | 유지(호환) | `ExcelReader`와 `HierarchyProcessor`를 합친 과거 계약입니다. 실제 처리는 두 구현 클래스에 위임합니다. 외부 import 전환 공지가 끝난 major 버전에서만 제거를 검토합니다. |
| `src/cli_excel_utils.py` | 내부 runtime 사용 없음 | 유지(호환) | 과거 CLI helper import를 보존하며 `ExcelReader`에 위임합니다. 새 코드는 직접 `ExcelReader`를 사용합니다. 패키지 외부 사용 여부를 확인할 수 있는 major 버전 전에는 제거하지 않습니다. |

## 운영 규칙

- 새 코드와 문서는 `cli_main.py`, `ExcelReader`, `HierarchyProcessor`를 사용합니다.
- 호환 wrapper에는 분기, cache, schema 해석 같은 업무 규칙을 추가하지 않습니다.
- wrapper를 제거할 때는 저장소 검색뿐 아니라 배포 사용자 공지와 major 버전 변경이
  필요합니다.
- `tests/test_compatibility_wrappers.py`가 위임 계약을 고정합니다.
