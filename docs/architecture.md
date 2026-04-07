# 아키텍처

## 개요

이 프로젝트는 Excel 기반 계층형 테스트 데이터를 Codebeamer Tracker Item으로 변환하고 업로드하는 자동화 파이프라인입니다.

코드베이스는 크게 다섯 계층으로 나뉩니다.

1. 엔트리 포인트
2. Excel 처리
3. 스키마 및 매핑
4. Payload 모델링 및 오케스트레이션
5. Codebeamer API 접근

## 주요 모듈

### 엔트리 포인트

- `cli_main_v2.py`: 실제 사용을 위한 권장 인터랙티브 CLI
- `cli_main.py`: 비교 및 참고용 레거시 CLI
- `main.py`: 과거 프로토타입 성격의 엔트리 포인트, 현재 비권장

### Excel 처리

`src/excel_processor.py`

주요 책임:
- `xlwings`로 워크북과 시트를 열기
- 헤더와 데이터 행 읽기
- summary 셀의 들여쓰기 수준 감지
- 여러 물리적 행을 하나의 논리 레코드로 병합
- 들여쓰기 기준으로 parent-child 관계 계산
- wizard가 사용하는 upload dataframe 생성

주요 산출물:
- `raw_df`
- `merged_df`
- `hierarchy_df`
- `upload_df`

### 스키마 및 매핑

레거시:
- `src/mapping_service.py`

현재 권장:
- `src/mapping_service_v2.py`

주요 책임:
- tracker schema를 dataframe 형태로 평탄화
- upload 컬럼과 schema 필드 비교
- option 성격의 필드 감지
- schema의 정적 options로 이름 매핑 테이블 생성
- Excel option 값 검증
- 지원되는 option 값을 Codebeamer reference 형식으로 변환

v2 개선점:
- 감지 기준이 `has_options` 하나에만 의존하지 않음
- `reference_type`, `Choice` value model, reference field type도 함께 감지
- 정적 option이 없는 reference 필드를 조용히 누락하지 않고 명시적으로 드러냄

### Payload 모델과 상태

`src/models.py`

주요 책임:
- reference 및 field value payload 모델 정의
- `to_dict()` 기반 payload 안전 직렬화
- `WizardState` 로 업로드 세션 상태 표현
- `TrackerItemBase` 를 통해 tracker item payload 구성

핵심 모델:
- `TrackerItemBase`
- `ChoiceFieldValue`
- `TextFieldValue`
- `TableFieldValue`
- `WizardState`

### 오케스트레이션

레거시:
- `src/wizard.py`

현재 권장:
- `src/wizard_v2.py`

주요 책임:
- API client, excel processor, mapping service를 조합해 전체 흐름 제어
- 업로드 세션 상태 유지
- Excel 헤더에서 `TableField` 컬럼 감지
- row 단위 payload preview 생성
- parent-first 순서로 업로드 수행
- 실행 산출물 저장

v2 개선점:
- `TableFieldValue` 객체를 업로드 전에 안전하게 dict로 직렬화
- payload 전체를 재귀적으로 정규화해서 요청 전송 안정성 향상
- unresolved reference lookup 필드를 preview/upload 시 명확하게 실패 처리

### API 접근

`src/codebeamer_client.py`

주요 책임:
- 인증 세션 구성
- 프로젝트, 트래커, 스키마, 아이템 조회
- 신규 tracker item 생성

## End-to-End 흐름

1. 사용자가 `cli_main_v2.py`를 실행합니다.
2. CLI가 config, logger, client, processor, mapper, wizard를 초기화합니다.
3. 사용자가 project와 tracker를 선택합니다.
4. wizard가 Excel을 읽고 dataframe들을 생성합니다.
5. Codebeamer에서 schema를 가져옵니다.
6. CLI가 Excel과 schema 매핑을 확인합니다.
7. v2 mapping service가 option-like 필드를 감지합니다.
8. 가능한 정적 option은 reference 값으로 해석합니다.
9. reference lookup이 필요한 필드는 별도로 표시합니다.
10. wizard가 payload preview를 생성합니다.
11. wizard가 parent-first 순서로 업로드합니다.
12. state와 실행 결과를 `output/`에 저장합니다.

## 상태 모델

`WizardState`는 업로드 파이프라인 전체의 스냅샷 역할을 합니다.

일반적인 생명주기:
- 먼저 `project_id`, `tracker_id`가 선택됨
- Excel 읽기 후 `raw_df`, `merged_df`, `hierarchy_df`, `upload_df`가 채워짐
- schema 로딩 후 `schema`, `schema_df`, `comparison_df`가 채워짐
- option 처리 후 `option_candidates_df`, `option_maps`, `option_check_df`, `converted_upload_df`가 채워짐
- upload 수행 후 `upload_result`가 채워짐

## TableField 처리 방식

기대하는 Excel 헤더 형식:
- `TableFieldName.ColumnName`

처리 흐름:
1. schema flattening 단계에서 `TableField` 정의와 하위 컬럼 목록 식별
2. wizard가 일치하는 Excel 컬럼 탐지
3. row 값들을 `TableFieldValue` 구조로 묶음
4. v2에서 업로드 전에 plain dict로 변환

## Option 및 Reference 처리 방식

정적 option 처리:
- schema에 `options` 배열이 있음
- Excel 값과 option 이름을 비교
- `{id, name, type}` 형태의 reference dict로 변환

reference lookup 처리:
- schema에는 reference type이 있으나 정적 options는 없음
- v2는 이를 `reference_lookup` 으로 분류
- 검증 단계에서 `OPTION_SOURCE_UNAVAILABLE` 표시
- unresolved 값이 남아 있으면 payload preview/upload 시 명확한 오류 발생

## 권장 조합

현재 가장 권장되는 실행 조합:
- `cli_main_v2.py`
- `src/mapping_service_v2.py`
- `src/wizard_v2.py`

## UML 문서

- `docs/class-diagram.puml`
- `docs/upload-sequence.puml`
