# GUI 리팩토링 진행 및 검증 기록

최종 갱신: 2026-07-29

## 목표

GUI를 주 실행 경로로 유지하면서 대형 모듈의 책임을 분리하고, 기존 공개 호출 경로와
업로드 동작을 보존한다. 기능 추가가 아니라 구조 개선이 목적이며 다음 원칙을 적용했다.

- 기존 facade와 page factory는 호환 경로로 유지한다.
- 파일별 workbook/raw data/cache를 재사용하고 명시적인 `데이터 불러오기` 흐름을 유지한다.
- create, update, upsert 검증 범위와 payload 규칙을 변경하지 않는다.
- `TableFieldValue`의 중첩 payload와 TRACKER configuration 기반 query 해석을 보존한다.
- 다중 파일, 파일별 루트 항목, 그룹 폴더, 기본값/수동값 입력 흐름의 회귀를 막는다.

## 완료한 구조 개선

### GUI 서비스

- `BatchValidationService`가 다중 파일 cache 구성과 검증 결과 집계를 담당한다.
- `BatchUploadService`가 파일별 wizard 준비, batch 실행, 결과 집계를 담당한다.
- `UploadService`는 두 서비스를 조합하는 facade로 남겼다.
- 루트 항목, tracker configuration, validation 표현 책임은 각각 독립 서비스로 분리했다.

### Wizard

- option 해석과 적용은 `wizard_option_resolution.py`로 분리했다.
- create payload와 `TableFieldValue` 구성은 `wizard_item_builder.py`로 분리했다.
- row별 payload cache와 preview는 `wizard_payload_cache.py`로 분리했다.
- `wizard_operations.py`는 create/update/upsert 실행과 결과 저장만 담당한다.
- `CodebeamerUploadWizard`의 기존 public 메서드는 facade로 유지했다.

### MainWindow와 페이지

- `MainWindow`는 런타임 내부 클래스를 만들지 않고 `QMainWindow`를 직접 상속한다.
- mapping/validation context와 upload progress를 구체 dataclass로 관리한다.
- 현재 mixin 조합은 정적 MRO와 구체 타입으로 충분하므로 별도 `Protocol`은 추가하지 않았다.
- 파일, 루트 항목, 매핑, 업로드 화면은 실제 `QWidget` 하위 클래스로 전환했다.
- 기존 `create_*_page` 함수는 호환용 생성 facade로 유지했다.

### 테스트와 유지보수

- 대형 GUI 서비스 회귀 테스트를 mapping, lookup, root item, batch, validation 영역으로 나눴다.
- 구현을 반복 설명하는 저가치 템플릿 docstring을 제거했다.
- 과거 entry point와 Excel wrapper의 유지 기준은 `docs/compatibility.md`에 기록했다.
- sample과 fixture의 익명화 및 자격증명 추적 방지는 자동 테스트로 고정했다.

## 자동 검증

실행 명령:

```powershell
.\codebeamer\Scripts\python.exe -m unittest discover -s tests
```

결과:

- 총 193개 테스트 통과
- GUI page/window/service 회귀 테스트 통과
- mapping/lookup/root item/batch validation/batch upload 회귀 테스트 통과
- wizard option/create/update/cache 및 `TableFieldValue` payload 회귀 테스트 통과
- 호환 wrapper와 sample 데이터 보안 감사 통과

## 수동 GUI 검증

검증 환경:

- Windows
- offline snapshot 기반 테스트 모드
- 일반 창 `862x665`
- 최대화 창 `1920x1032`
- 테마: KEFICO, IGLOO

확인한 화면:

- 설정
- 프로젝트
- 파일
- 상단 구조
- 상단 필드
- 매핑
- 검증
- 업로드
- 결과

검증 시나리오:

1. 익명화 sample Excel 2개를 한 번에 선택했다.
2. 옵션 변경만으로 자동 재로딩되지 않는 것을 확인했다.
3. 명시적인 `데이터 불러오기` 후 2개 파일 preview와 다음 단계 활성화를 확인했다.
4. 파일별 루트 항목 2개와 루트 필드 assignment를 확인했다.
5. 매핑 테이블이 일반 창과 최대화 창에서 가로·세로로 확장되는 것을 확인했다.
6. offline snapshot에서 source tracker query를 수행할 수 없는 `Related Requirement` 매핑은
   지원을 가장하지 않고 검증 단계에서 차단되는 것을 확인했다.
7. 해당 선택 필드를 create 범위에서 제외한 뒤 예상 항목 6행 모두 검증을 통과했다.
8. 테스트 모드가 Dry Run을 강제하는 것을 확인했다.
9. Dry Run은 파일 루트 2건과 데이터 6건, 총 8건을 처리해 성공 8건, 실패 0건,
   재시도 0건으로 완료됐다.
10. 결과 화면의 성공·실패·미해결 탭과 성공 8개 행을 확인했다.
11. 새 업로드 흐름으로 처음 화면에 복귀하고 두 테마의 레이아웃을 확인한 뒤
    기본 KEFICO 테마로 원복했다.

## 관련 커밋

- `4008aa6` 배치 검증과 업로드 분리
- `c03c7a0` wizard payload 생성 책임 분리
- `eaf9e1a` 창 상태와 진행 상태 타입화
- `5e95293` 핵심 페이지를 `QWidget` 클래스로 전환
- `59ce2b2` 서비스 회귀 테스트를 도메인별로 분할
- `48f652d` 저가치 템플릿 docstring 제거
- `1787878` 호환 wrapper 유지 기준 기록
- `8c56528` sample 데이터 보안 감사 자동화

## 남은 운영 과제

이번 리팩토링 범위의 미완료 항목은 없다. 다음 작업은 구조 개선이 아니라 별도 기능 또는
운영 과제로 분리한다.

- 실제 서버 자격증명으로 live upload smoke test 수행
- `Status` 변경을 위한 transition 기반 전처리 구현
- 새로운 field/configuration 조합이 추가될 때 지원 여부와 fallback 정책 갱신

