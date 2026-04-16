# Codebeamer Automation Suite

Excel 기반 계층형 데이터를 Codebeamer Tracker Item으로 변환하고 업로드하는 자동화 도구입니다.

현재 기본 실행 경로는 `cli_main.py`이며, 예전 `v2` 경로의 개선 사항은 모두 원본 모듈에 반영되어 있습니다.

GUI 1차 스켈레톤 엔트리 포인트는 `gui_main.py` 입니다.

## 현재 지원하는 핵심 기능

- Excel 시트에서 계층형 데이터 읽기
- 입력단 분리: Excel reader와 DataFrame 기반 hierarchy processor 분리
- Tracker schema 조회 및 Excel 컬럼과의 자동 매핑 확인
- schema의 `multipleValues=true` 필드에 대응하는 Excel 컬럼 자동 list 처리
- 정적 option 값을 Codebeamer reference payload로 변환
- `UserChoiceField`, `UserReference` 필드에 대해 사용자 이름 우선 lookup 후 reference로 변환
- `MemberField` 는 `USER/ROLE/GROUP` 타입별 후보를 이름으로 찾아 mixed reference로 변환
- `TrackerItemChoiceField` 및 builtin `subjects` 필드에 대해 tracker item ID를 파싱해 `TrackerItemReference`로 변환
- 사용자 lookup 결과를 프로젝트 단위 임시 캐시에 저장해 반복 요청 최소화
- `TableFieldName.ColumnName` 형식 헤더를 이용한 `TableField` 조립
- row별 payload cache 생성과 preview/upload 재사용
- parent-first 순서 보장 업로드
- 실행 결과와 중간 산출물 저장
- PySide6 기반 GUI 스켈레톤
- GUI 설정 저장 및 암호화된 비밀번호 저장
- GUI에서 연결 테스트, 프로젝트/트래커 조회, Excel 시트/미리보기 조회
- GUI에서 컬럼 매핑, 검증, 업로드, 결과 화면의 1차 연결

## 권장 실행 명령

```bash
py -3 cli_main.py
```

GUI 스켈레톤 실행:

```bash
py -3 gui_main.py
```

## GUI 구현 현황

현재 `feature/upload-gui` 브랜치 기준 GUI에서 실제로 연결된 범위는 다음과 같습니다.

- 설정 화면
  - 설정 불러오기/저장
  - 비밀번호 저장 체크박스
  - `cryptography` 기반 비밀번호 암호화 저장
  - 연결 테스트
  - 프로젝트/트래커 조회
- 파일 선택 화면
  - Excel 파일 선택
  - 시트 목록 조회
  - 헤더/미리보기 조회
  - Summary 컬럼 자동 제안
- 컬럼 매핑 화면
  - 업로드 대상 컬럼 표시
  - `id`, `parent` 제외
  - 체크박스/콤보박스 기반 1차 매핑
  - 검증 실행 연결
- 검증 화면
  - `comparison_df`, `option_check_df`, `payload_df` 실패 정보 표시
- 업로드 화면
  - worker 기반 실행
  - progress 갱신
  - pause / resume / cancel 플래그 처리
  - 로그 및 실패 응답 JSON 표시
- 결과 화면
  - 성공 / 실패 / 미해결 결과 테이블 표시

아직 남아 있는 항목:

- 컬럼 매핑 UX 개선
- 결과 화면 상세 상호작용 개선
- 실제 GUI 수동 테스트와 예외 케이스 보강
- `PyInstaller` 배포 스크립트 정리

## 프로젝트 구조

- `cli_main.py`: 현재 권장 대화형 CLI
- `main.py`: 과거 엔트리 포인트, 현재 비권장
- `src/codebeamer_client.py`: Codebeamer REST API 클라이언트
- `src/excel_reader.py`: Excel 파일을 raw DataFrame으로 읽는 입력 계층
- `src/hierarchy_processor.py`: raw DataFrame을 merged/hierarchy/upload DataFrame으로 후처리
- `src/excel_processor.py`: 기존 import 호환용 통합 래퍼
- `src/mapping_service.py`: schema flattening, 컬럼 비교, option/reference 처리
- `src/wizard.py`: 업로드 오케스트레이션, preview, 업로드, 상태 저장
- `src/models/`: reference, field value, tracker item, user info, wizard state 모델
- `src/gui/`: PySide6 기반 단계형 GUI, 서비스 계층, upload worker
- `docs/`: 사용 가이드와 아키텍처 문서
- `output/`: 실행 결과 산출물 저장 디렉터리

## 빠른 시작

1. 의존성 설치

```bash
pip install -r requirements.txt
```

2. `.env` 설정

```env
CODEBEAMER_BASE_URL=https://your-codebeamer-host/cb
CODEBEAMER_USERNAME=your_username
CODEBEAMER_PASSWORD=your_password
DEFAULT_PROJECT_ID=
DEFAULT_TRACKER_ID=
EXCEL_HEADER_ROW=1
EXCEL_SHEET_NAME=0
LOG_LEVEL=INFO
OUTPUT_DIR=output
```

3. CLI 실행

```bash
py -3 cli_main.py
```

## 현재 처리 흐름

1. Codebeamer에서 프로젝트, 트래커, schema 메타데이터를 조회합니다.
2. Excel 헤더와 schema를 비교해 컬럼 매핑을 확인합니다.
3. `multipleValues=true` 필드에 매핑된 Excel 컬럼을 자동으로 list 컬럼으로 선택합니다.
4. Excel reader가 raw dataframe과 `_excel_row`, `_summary_indent` 메타정보를 생성합니다.
5. hierarchy processor가 멀티라인 병합과 parent-child 계층 구성을 수행합니다.
6. 정적 option 필드는 reference payload로 변환합니다.
7. 사용자 선택 필드는 사용자 이름을 우선 조회하고, 숫자 입력일 때만 사용자 ID fallback 을 사용합니다.
8. `MemberField` 는 `USER/ROLE/GROUP` 후보를 이름으로 찾아 mixed reference 로 변환합니다.
9. `TrackerItemChoiceField` 와 builtin `subjects` 는 입력값에서 tracker item ID를 파싱해 `TrackerItemReference`로 변환합니다.
10. row별 payload를 먼저 cache하고 preview와 upload가 같은 payload를 재사용합니다.
11. 업로드 시점에는 parentItemId만 `created_map[parent_row_id]` 기준으로 결정합니다.
12. `Status` 는 transition 기반 후처리로 옮겨야 하므로 현재 TODO 로 남겨두고 있습니다.
13. 실행 결과와 중간 dataframe, schema, payload cache, 검증 결과를 `output/`에 저장할 수 있습니다.

## 문서

- [문서 허브](./docs/index.md)
- [아키텍처](./docs/architecture.md)
- [CLI 사용 가이드](./docs/cli-guide.md)
- [GUI 설계 초안](./docs/gui-plan.md)
- [변경 이력 성격의 v2 문서](./docs/v2-changes.md)
- [트러블슈팅](./docs/troubleshooting.md)

## UML 렌더링

PlantUML이 준비된 환경에서는 아래 스크립트로 UML 이미지를 생성할 수 있습니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_uml.ps1
```

생성 대상:
- `docs/class-diagram.png`
- `docs/class-diagram.svg`
- `docs/upload-sequence.png`
- `docs/upload-sequence.svg`

## 참고 사항

- `TableField` 컬럼은 `TableFieldName.ColumnName` 형식의 Excel 헤더를 기준으로 감지합니다.
- 정적 option이 없는 일반 reference 필드는 아직 자동 lookup을 모두 지원하지 않습니다.
- 사용자 관련 필드는 이름을 우선 사용하고, 숫자 입력일 때만 사용자 ID fallback 을 사용합니다.
- `MemberField` 의 `ROLE` 은 field permission matrix, `GROUP` 은 `/v3/users/groups` 전체 목록에서 이름으로 찾습니다.
- `TrackerItemChoiceField` 와 builtin `subjects` 는 각 값에서 `[:id]` 패턴을 먼저, 없으면 `[]` 안 첫 번째 정수를 사용해 `TrackerItemReference`를 만듭니다.
- `Status` 는 workflow transition 제약을 반영해야 하므로 현재 TODO 입니다.
- `save_state()`는 `payload_df.csv`, `payload_preview.jsonl`을 포함해 payload cache 상태도 함께 저장합니다.
