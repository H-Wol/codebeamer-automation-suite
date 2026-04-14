# CLI 사용 가이드

## 권장 실행 명령

```bash
py -3 cli_main.py
```

## 현재 CLI 특징

- tracker schema를 먼저 읽고 Excel 헤더와의 자동 매핑을 확인합니다.
- schema의 `multipleValues=true` 필드에 매핑된 Excel 컬럼은 자동으로 list 컬럼으로 처리합니다.
- 정적 option 필드는 reference payload로 자동 변환합니다.
- `UserChoiceField`, `MemberField`, `UserReference` 필드는 사용자 ID lookup 후 reference로 변환하고, 같은 사용자 ID에 대한 결과는 프로젝트 단위로 캐시합니다.
- `TrackerItemChoiceField` 와 builtin `subjects` 는 tracker item ID를 파싱해 `TrackerItemReference`로 변환합니다.
- payload preview를 확인한 뒤 dry-run 또는 실제 업로드를 수행할 수 있습니다.

## 요구 사항

- Python 3
- 환경에 따라 `xlwings` 가 요구하는 Excel 설치
- 대상 Codebeamer 서버 접근 네트워크
- 올바르게 설정된 `.env`

## 설치

```bash
pip install -r requirements.txt
```

## 환경 변수

필수:
- `CODEBEAMER_BASE_URL`
- `CODEBEAMER_USERNAME`
- `CODEBEAMER_PASSWORD`

선택:
- `DEFAULT_PROJECT_ID`
- `DEFAULT_TRACKER_ID`
- `EXCEL_HEADER_ROW`
- `EXCEL_SHEET_NAME`
- `LOG_LEVEL`
- `OUTPUT_DIR`

예시:

```env
CODEBEAMER_BASE_URL=https://your-codebeamer-host/cb
CODEBEAMER_USERNAME=your_username
CODEBEAMER_PASSWORD=your_password
EXCEL_HEADER_ROW=1
EXCEL_SHEET_NAME=0
LOG_LEVEL=INFO
OUTPUT_DIR=output
```

## 기대하는 Excel 형식

CLI는 다음 구조를 전제로 합니다.

- 하나의 summary 컬럼이 논리 레코드의 제목 역할을 함
- summary 셀의 들여쓰기로 계층 표현
- 여러 물리적 행이 하나의 논리 레코드를 표현할 수 있음
- list처럼 취급할 컬럼은 수동 선택이 아니라 schema의 `multipleValues=true` 여부와 컬럼 매핑 결과로 자동 결정됨
- `TableField` 는 `TableFieldName.ColumnName` 형식 헤더 사용

## 인터랙티브 흐름

1. project 선택
2. tracker 선택
3. Excel 파일 및 sheet 선택
4. summary 컬럼 자동 감지 또는 수동 선택
5. tracker schema 조회
6. Excel 헤더와 schema의 자동 매핑 확인
7. `multipleValues=true` 필드에 대응하는 list 컬럼 자동 선택
8. Excel 읽기, 멀티라인 병합, 계층 생성
9. schema 비교 결과 확인
10. option/reference 필드 검증 결과 확인
11. 사용자 선택 필드가 있으면 사용자 ID lookup 및 캐시 반영
12. tracker item 선택 필드가 있으면 tracker item ID 파싱
13. payload preview 확인
14. dry-run 또는 실제 업로드 수행
15. 실행 결과 저장 여부 선택

## 산출물

wizard는 다음 결과를 저장할 수 있습니다.

- `raw_df`, `merged_df`, `hierarchy_df`, `upload_df`
- `converted_upload_df`
- `schema_df`, `comparison_df`
- `option_check_df`
- `success_df`, `failed_df`, `unresolved_df`
- `schema.json`, `option_maps.json`, `created_map.json`

## lookup 관련 참고

- 사용자 lookup 결과는 `__resolved`, `__user_info`, `__lookup_status`, `__lookup_error` 컬럼에 반영됩니다.
- 같은 프로젝트 안에서 동일한 사용자 ID는 재사용 캐시로 처리됩니다.
- `__user_info` 는 `{id, name, type="UserReference"}` 최소 구조로 저장됩니다.
- `TrackerItemChoiceField` 와 builtin `subjects` 는 lookup 없이 입력값에서 tracker item ID를 직접 파싱합니다.
- 정적 option이 없는 일반 reference field는 아직 자동 lookup을 모두 지원하지 않습니다.

## 레거시 엔트리 포인트

- `main.py`: 과거 엔트리 포인트, 현재 비권장
