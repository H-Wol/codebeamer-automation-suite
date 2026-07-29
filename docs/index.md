# 문서 허브

`Codebeamer Automation Suite` 문서의 시작점입니다.

## 권장 읽기 순서

1. [README](../README.md)
2. [아키텍처](./architecture.md)
3. [Codebeamer 업로드 조사 정리](./codebeamer-upload-reference.md)
4. [Codebeamer 프로젝트 시작 패키지](./codebeamer-project-start-kit.md)
5. [CLI 사용 가이드](./cli-guide.md)
6. [필드 지원 추가 가이드](./field-support-guide.md)
7. [GUI 사용 가이드](./gui-plan.md)
8. [트러블슈팅](./troubleshooting.md)
9. [v2 변경 사항](./v2-changes.md)

## 문서별 역할

- [README](../README.md)
  저장소 소개, 빠른 시작, 현재 기본 실행 경로를 요약합니다.

- [아키텍처](./architecture.md)
  코드 구조, 모듈 책임, 상태 모델, 최신 업로드 순서도를 설명합니다.

- [Codebeamer 업로드 조사 정리](./codebeamer-upload-reference.md)
  다른 프로젝트에서 재사용할 수 있도록 Codebeamer 업로드에 필요한 API, schema 규칙, payload 규칙, 한계를 한 문서로 묶었습니다.

- [Codebeamer 프로젝트 시작 패키지](./codebeamer-project-start-kit.md)
  live tracker schema export와 시작 템플릿을 함께 사용하는 권장 시작 절차를 정리합니다.

- [CLI 사용 가이드](./cli-guide.md)
  실행 방법, Excel 입력 형식, 자동 매핑과 자동 list 컬럼 선택 흐름을 설명합니다.

- [필드 지원 추가 가이드](./field-support-guide.md)
  새로운 schema field type 또는 reference field를 지원할 때 수정해야 하는 코드 경로와 구현 순서를 설명합니다.

- [GUI 사용 가이드](./gui-plan.md)
  사용자용 GUI 의 실제 단계별 사용 흐름, 테스트 모드, 다중 파일 업로드, 상단 데이터 설정, 현재 구현 범위를 정리합니다.

- [트러블슈팅](./troubleshooting.md)
  자주 발생하는 에러와 대응 방법을 정리합니다.

- [v2 변경 사항](./v2-changes.md)
  예전 `v2` 도입 배경과 이후 원본 경로에 반영된 주요 개선 이력을 기록합니다.

## UML 및 흐름 문서

- [클래스/의존 관계 UML](./class-diagram.puml)
- [업로드 시퀀스 UML](./upload-sequence.puml)
- [UML 렌더링 가이드](./render-uml.md)
- 최신 mermaid 업로드 순서도는 [아키텍처 문서](./architecture.md)에 포함되어 있습니다.

## 현재 기준 권장 코드 경로

- `cli_main.py`
- `src/mapping_service.py`
  facade이며 실제 schema/reference/option 로직은 `src/mapping_reference.py`, `src/mapping_schema.py`, `src/mapping_option.py` 로 분리되어 있습니다.
- `src/wizard.py`
  facade이며 실제 데이터 준비, lookup, payload, 실행 로직은 `src/wizard_data.py`, `src/wizard_user_lookup.py`, `src/wizard_tracker_lookup.py`, `src/wizard_payload.py`, `src/wizard_operations.py` 로 분리되어 있습니다.
- `src/models/`
- `src/gui/`
  메인 진입점은 `src/gui/main_window.py`, `src/gui/pages.py`, `src/gui/services.py` 이고, 내부 책임은 page/window/service 하위 모듈로 분리되어 있습니다.
