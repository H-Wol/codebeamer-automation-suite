# v2 변경 사항

## 요약

v2 경로는 payload 생성 안정성과 option/reference 처리의 명확성을 높이기 위해 추가되었습니다.

대상 파일:
- `src/mapping_service_v2.py`
- `src/wizard_v2.py`
- `cli_main_v2.py`

## 핵심 개선 사항

### 1. 안전한 `TableFieldValue` 직렬화

레거시 경로의 문제:
- `TableFieldValue` 객체가 `payload["customFields"]` 내부에 그대로 남을 수 있었음
- HTTP 요청의 JSON 직렬화는 plain dict/list를 기대함

v2 동작:
- `TableFieldValue` 객체를 payload에 붙이기 전에 dict로 변환
- 최종 payload 전체를 재귀적으로 정규화 후 전송

관련 구현:
- `CodebeamerUploadWizardV2._build_table_custom_fields()`
- `CodebeamerUploadWizardV2._serialize_payload_value()`
- `CodebeamerUploadWizardV2.preview_payload()`

### 2. option-like 필드 감지 범위 확장

레거시 한계:
- 감지 로직이 사실상 schema의 정적 `options` 존재 여부에 치우쳐 있었음

v2 동작:
- 정적 option 필드는 계속 지원
- `reference_type` 이 있는 필드도 감지
- `Choice` value model을 가진 필드도 감지
- `ReferenceField`, `OptionChoiceField` 타입도 감지

관련 구현:
- `MappingServiceV2._is_option_like_field()`
- `MappingServiceV2.get_option_field_candidates()`

### 3. unresolved reference 필드의 명시적 처리

레거시 한계:
- 일부 reference 필드는 비교 단계에서는 중요해 보이지만 실제 resolution 단계에서 조용히 빠질 수 있었음

v2 동작:
- 이런 필드를 `reference_lookup` 으로 분류
- 검증 단계에서 `OPTION_SOURCE_UNAVAILABLE` 보고
- preview/upload 시 unresolved 값이 남아 있으면 명확하게 실패

관련 구현:
- `MappingServiceV2.build_option_maps_from_schema()`
- `MappingServiceV2.check_option_alignment()`
- `CodebeamerUploadWizardV2._resolve_option_field_value()`

## 현재 v2의 경계

v2는 아직 모든 reference type에 대한 동적 lookup을 구현하지는 않았습니다.

즉, 지금은 이런 필드들을 숨기지 않고 정확히 드러내지만, schema에 정적 options가 없는 경우 자동 해결까지는 하지 않습니다.

향후 lookup이 필요할 수 있는 예:
- `UserReference`
- `TrackerItemReference`
- 별도 endpoint 조회가 필요한 custom reference field

## 다음 확장 포인트

reference backed field를 완전 자동화하려면, 다음 단계가 자연스럽습니다.
- `reference_type` 별 lookup provider 구현
- `MappingServiceV2` 와 `CodebeamerUploadWizardV2` 에 lookup 분기 연결
- 캐시 전략과 이름 충돌 처리 추가
