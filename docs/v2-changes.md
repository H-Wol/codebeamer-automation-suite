# v2 변경 사항

## 문서 성격

이 문서는 예전 `v2` 경로 도입 배경과 그 이후 원본 경로에 반영된 개선 이력을 기록합니다.

현재 기준:
- `cli_main.py`
- `src/mapping_service.py`
- `src/wizard.py`
- `src/models/`

위 경로들이 기본 경로이며, 과거 `v2` 변경 내용은 이미 이 파일들에 흡수되어 있습니다.

## 초기에 도입된 핵심 개선

### 1. 안전한 `TableFieldValue` 직렬화

- `TableFieldValue` 객체를 payload에 붙이기 전에 dict로 변환
- 최종 payload 전체를 재귀적으로 정규화해 JSON 직렬화 안정성 확보

관련 구현:
- `CodebeamerUploadWizard._build_table_custom_fields()`
- `CodebeamerUploadWizard._serialize_payload_value()`
- `CodebeamerUploadWizard.preview_payload()`

### 2. option-like 필드 감지 범위 확장

- 정적 option 필드는 계속 지원
- `reference_type` 이 있는 필드도 감지
- `Choice` value model을 가진 필드도 감지
- `ReferenceField`, `OptionChoiceField` 타입도 감지

관련 구현:
- `MappingService._is_option_like_field()`
- `MappingService.get_option_field_candidates()`

### 3. unresolved reference 필드의 명시적 처리

- 자동 해결이 불가능한 reference field를 조용히 누락하지 않음
- 검증 단계에서 `OPTION_SOURCE_UNAVAILABLE` 로 드러냄
- preview/upload 시 unresolved 값이 남아 있으면 명확하게 실패

관련 구현:
- `MappingService.build_option_maps_from_schema()`
- `MappingService.check_option_alignment()`
- `CodebeamerUploadWizard._resolve_option_field_value()`

## 이후 원본 경로에 반영된 후속 개선

### 1. 모델 패키지 분리

- `src/models.py` 단일 파일을 `src/models/` 패키지로 분리
- reference, field value, tracker item, wizard state 책임을 모듈별로 정리

### 2. registry 기반 생성 로직

- `_build_reference()` 와 `_build_field_value()` 의 하드코딩 분기를 registry 패턴으로 정리
- 새 타입 추가 시 팩토리 함수의 `if/elif` 체인을 늘리지 않아도 됨

### 3. 타입과 상태 문자열의 공통 enum화

- reference type, field value type, schema field type
- option map kind, lookup status, upload status

위 토큰을 `src/models/common.py` 에서 공통 enum/상수로 관리

### 4. 사용자 선택 필드와 tracker item 선택 필드 처리 확장

- `UserReference`, `UserChoiceField` 는 사용자 이름 우선 조회 후 reference로 변환
- `MemberField` 는 `USER/ROLE/GROUP` 후보를 이름으로 찾아 mixed reference로 변환
- `TrackerItemChoiceField` 와 builtin `subjects` 는 tracker item ID를 직접 파싱해 `TrackerItemReference` 로 변환
- `__user_info`, `__resolved`, `__lookup_status`, `__lookup_error` 를 남김

### 5. 사용자/member lookup 캐시

- 같은 프로젝트 내에서 같은 사용자 이름/ID, 같은 member 이름을 반복 조회하지 않도록 캐시 도입
- 캐시는 `WizardState.user_lookup_cache`, `member_lookup_cache`, `group_lookup_cache`, `tracker_role_cache` 로 분리

### 6. `multipleValues` 기반 list 컬럼 자동 선택

- 수동 list 컬럼 선택 단계를 제거
- schema의 `multipleValues=true` 필드에 매핑된 Excel 컬럼을 자동으로 list 처리

## 다음 확장 포인트

현재 자동화가 아직 완전하지 않은 영역은 다음과 같습니다.

- `TrackerItemReference` 자동 lookup
- `ProjectReference`, `RepositoryReference` 같은 기타 reference field lookup
- `Status` transition 기반 후처리
- pagination 및 대량 검색 전략 정교화
- lookup 실패 시 재시도 정책 또는 별도 사용자 피드백 UI
