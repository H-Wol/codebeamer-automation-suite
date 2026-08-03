# Codebeamer Automation Suite

Excel 기반 계층형 데이터를 Codebeamer Tracker Item으로 변환하고 업로드하는 자동화 도구입니다.

현재 기본 실행 경로는 `gui_main.py`이며, `cli_main.py`는 유지보수와 보조 실행에 사용합니다.
예전 `v2` 경로의 개선 사항은 원본 모듈에 반영되어 있고, GUI도 같은 업로드 파이프라인을 재사용합니다.

## 현재 지원하는 핵심 기능

- Excel 시트에서 계층형 데이터 읽기
- 입력단 분리: Excel reader와 DataFrame 기반 hierarchy processor 분리
- Tracker schema 조회 및 Excel 컬럼과의 자동 매핑 확인
- schema의 `multipleValues=true` 필드에 대응하는 Excel 컬럼 자동 list 처리
- 정적 option 값을 Codebeamer reference payload로 변환
- `UserChoiceField`, `UserReference` 필드에 대해 사용자 이름 우선 lookup 후 reference로 변환
- `MemberField` 는 `USER/ROLE/GROUP` 타입별 후보를 이름으로 찾아 mixed reference로 변환
- `TrackerItemChoiceField` 및 builtin `subjects` 필드에 대해 정규식 ID 추출 또는 configuration 기반 tracker item query lookup 지원
- 사용자 lookup 결과를 프로젝트 단위 임시 캐시에 저장해 반복 요청 최소화
- `TableFieldName.ColumnName` 형식 헤더를 이용한 `TableField` 조립
- row별 payload cache 생성과 preview/upload 재사용
- parent-first 순서 보장 업로드
- 실행 결과와 중간 산출물 저장
- `트래커 작업공간`, `배치 작업`, `실행 기록`, `설정`을 전환하는 PySide6 앱 셸
- 데이터 영역을 넓게 쓸 수 있는 접이식 좌측 앱 메뉴와 실행 간 접힘 상태 복원
- `배치 작업` 안에서 기존 9단계 create/update/upsert 마법사 보존
- 이름이 있는 다중 연결 프로필과 활성 프로필 하나를 관리하는 전용 설정 센터
- 비밀번호의 로컬 암호화 저장을 기본으로 하고 OS 자격증명 저장소 또는 미저장 방식 선택
- 명시적 검증·저장·적용, credential 제외 설정 가져오기/내보내기와 legacy 설정 migration
- 전역 설정 페이지에서 테마와 테스트 모드용 offline schema/config/조회 데이터 snapshot 관리
- `설정 > 개발자`에서 켜는 별도 실시간 API 모니터와 최근 500개 호출의 상태·지연 통계
- 현재 tracker 범위를 강제하는 CbQL, 계층 전체 수집, 검색 pagination과 상세 정규화 조회 서비스
- 프로젝트·트래커 선택, 전체 스크롤 확장형 트리, tracker 범위 검색과 ID 바로 열기를 제공하는 작업공간
- schema 기반 최상위·하위 단건 생성, TableField 행 편집을 포함한 선택 필드 부분 수정, 단건 상태 전환, version 충돌 확인과 ID 재입력 삭제
- 단건 쓰기와 배치 최종 결과를 최근 500건까지 보관하는 필터형 통합 실행 기록
- GUI에서 프로젝트/트래커 조회, 다중 Excel 파일 선택, 시트/미리보기 조회
- GUI에서 상단 데이터 생성 여부, 파일명 정규식 파싱, 루트 필드 매핑 설정
- GUI에서 컬럼 매핑, 기본값 설정, tracker item query/regex 전략 선택
- GUI에서 파일/검증/업로드 단계의 백그라운드 실행과 로딩 오버레이 표시
- GUI에서 단계별 `다음` 버튼 활성화 조건과 검증 차단 정책 적용
- GUI 검증/결과 화면에서 내부 생성 컬럼 숨김
- GUI 업로드 화면에서 총 건수, 항목별 로그, 시작/완료 시각, 소요 시간 표시
- GUI 설정 화면 compact 레이아웃, 테스트 모드 배지, 1080 높이 대응 스크롤/높이 상한 적용
- GUI와 CLI 간 payload ready 판정 및 사용자 표시용 이슈 추출 기준 일치

## 권장 실행 명령

```bash
py -3 gui_main.py
```

CLI 보조 실행:

```bash
py -3 cli_main.py
```

## GUI 오프라인 예시 데이터

GUI의 최상위 `설정 > 테스트 모드`에서 사용할 수 있는 샘플 세트는 `data/gui-offline-sample/` 에 있습니다.

- `offline_schema.json`
- `offline_tracker_configuration.json`
- `offline_tracker_items.json`
- `files/SAMPLE_MODULE_A_TC_001.xlsx`
- `files/SAMPLE_MODULE_B_TC_002.xlsx`
- `files/SAMPLE_LOOKUP_TC_003.xlsx`

사용 순서와 매핑 팁은 [data/gui-offline-sample/README.md](./data/gui-offline-sample/README.md)에 정리했습니다.

## GUI 구현 현황

GUI를 실행하면 최상위 앱 셸이 열리고 `트래커 작업공간`, `배치 작업`, `실행 기록`, `설정`을 전환할 수 있습니다.
좌측 앱 메뉴는 상단 화살표로 접거나 펼칠 수 있습니다. 접힌 상태에서는 `조회`, `배치`, `기록`, `설정`의 짧은 이름과 전체 이름 툴팁을 제공하며, 상태는 다음 실행에도 복원됩니다.
현재 실제 업로드 흐름은 `배치 작업` 안에서 아래 9단계 마법사로 이어집니다.

- 최상위 설정 화면
  - `연결`, `화면`, `네트워크·저장소`, `테스트 모드`, `개발자`, `데이터 관리` 영역 전환
  - 여러 연결 프로필과 활성 프로필 하나 관리
  - 연결 또는 snapshot 검증 후 명시적으로 저장·적용
  - 로컬 암호화, OS 자격증명 저장소, 미저장 중 비밀번호 저장 방식 선택
  - 전역 설정 가져오기/내보내기에서 credential 제외
  - 테스트 모드의 익명 `조회 데이터 Snapshot` 선택과 검증
  - 개발자 영역에서 API 모니터 사용 여부와 느린 요청 기준 관리
- API 모니터
  - 별도 최대화 가능 창에서 요청 종류, method, 정규화 경로, status code, 소요 시간과 재시도 표시
  - 최근 최대 500개 HTTP 시도 기준 성공률, 오류, 평균·P50·P95·최대 지연, 최근 1분 요청과 429 통계
  - 검색·method·status·결과·느린 요청 필터, 화면 일시정지, 자동 스크롤, 선택 행 복사와 기록 지우기
  - 요청·응답 본문, header, query 값, host, 실제 ID와 원본 오류 문자열은 수집·저장하지 않음
- 트래커 작업공간
  - 프로젝트·트래커, 최상위 아이템 전체와 직접 하위 아이템 전체 조회
  - 서버 페이지를 백그라운드에서 끝까지 합쳐 하나의 스크롤 트리로 표시
  - 노드를 펼칠 때 직접 하위 전체를 조회하고 화면 세션 동안 결과 캐시
  - 선택한 tracker 안에서 ID/요약·상태·담당자 간편 검색
  - 전역 아이템 ID 바로 열기와 프로젝트·트래커·조상 경로 전환
  - 선택 아이템 설명, builtin/custom field와 민감값이 마스킹된 원본 JSON 조회
  - 상세 ID 배지를 클릭해 숫자 ID만 클립보드에 복사
  - 명시적 Wiki 형식 설명·필드 rich text 표시와 원문 전환
  - `TableField` 행·열 전용 보기와 Wiki로 선언된 셀만 선택적 렌더링
  - 검색 페이지 메타데이터와 늦게 끝난 백그라운드 요청을 구분하는 request token 적용
  - 선택 tracker schema 기반 최상위 또는 선택 아이템 하위 단건 생성
  - 생성 필수 필드 자동 포함, 선택 필드 명시 선택과 생성 직후 트리·상세 전환
  - 새 아이템 입력 창 전체 화면과 미지원 필드 숨김, 필수 미지원 필드 상단 차단 안내
  - schema 유형별 입력 widget과 변경할 필드 명시 선택
  - TableField 행 추가·복제·삭제·순서 변경, Wiki 미리보기, 숨김 셀 보존과 전체 화면 편집
  - 수정 탭의 미저장 입력 상태를 유지하는 별도 창·전체 화면 전환
  - 전체 리소스 교체가 아닌 `fieldValues` 부분 수정과 저장 전 version 재확인
  - 일반 필드 저장과 분리된 상태 전환, ID 재입력 확인이 필요한 삭제
  - 테스트 모드에서는 편집 구조만 표시하고 생성·수정·상태 전환·삭제 이중 차단
- 배치 설정 화면
  - 작업 모드, Header Row, Summary Column, Sheet Name 관리
  - 상단 `전체 설정 저장 / 불러오기`로 배치 preset 관리
  - 현재 전역 실행 환경 확인과 `전역 설정 열기`
- 프로젝트 화면
  - 온라인 모드 프로젝트/트래커 조회
  - 테스트 모드 snapshot 기반 프로젝트/트래커 자동 채움
- 파일 화면
  - 여러 Excel 파일 동시 선택
  - 대표 파일 미리보기 선택
  - `데이터 불러오기` 버튼으로만 시트/헤더/미리보기 재생성
  - Summary 컬럼 자동 제안
- 상단 데이터 화면
  - 파일별 상단 부모 데이터 생성 여부 선택
  - 파일명 또는 파일명 정규식 기반 source 선택
  - 정규식 실시간 미리보기
  - 루트 제목 필드는 파일명 기반으로, 다른 필드는 파일명 source 또는 고정값으로 설정
- 매핑 화면
  - `id`, `parent`, 내부 생성 컬럼 제외
  - 기본값 설정
  - `TrackerItemChoiceField` 별 regex/query 방식 선택
  - query 다건 결과 처리 전략 선택
- 검증 화면
  - 차단 이슈와 안내 이슈 분리
  - 다중 파일일 때 선택 파일 수와 전체 예상 항목 수 표시
  - 대표 파일 검증 결과 표시
- 업로드 화면
  - Dry Run / continue on error
  - 총 건수, 현재 항목, 성공/실패/재시도 수 표시
  - 항목별 시작/완료/소요 시간과 로그 표시
  - 실패 응답 JSON 표시
- 결과 화면
  - 성공 / 실패 / 미해결 탭
  - 내부 생성 컬럼 숨김

## 최근 GUI 보완 사항

- 최상위 앱 셸을 추가하고 기존 9단계 마법사를 `배치 작업` 컨테이너에 그대로 보존했습니다.
- 최상위 좌측 앱 메뉴를 접고 펼칠 수 있으며, 접힘 상태를 전역 설정에 저장하도록 구성했습니다.
- 전용 설정 센터를 구현하고 전역 연결·테마·재시도·출력·테스트 설정을 배치 preset에서 분리했습니다.
- 트래커 조회용 query/detail/page 모델과 최상위·하위·ID 경로 서비스를 추가하고, 두 tracker 익명 fixture로 범위 분리를 검증했습니다.
- `트래커 작업공간`에 프로젝트·트래커 선택, 페이지 구분 없는 전체 스크롤 계층, tracker 범위 검색, ID 직접 접근과 상세 화면을 연결했습니다.
- Wiki로 명시된 설명과 custom field만 안전한 rich text로 표시하고 `TableField` 행·열 전용 보기를 연결했습니다.
- 상세 `수정` 탭에 schema 기반 광범위 필드 편집, 단건 상태 전환과 안전한 삭제를 연결했습니다.
- `TableField` 중첩 행 구조를 보존하는 전용 편집기와 단건 생성·수정 화면의 확대 작업 흐름을 추가했습니다.
- `실행 기록`에 단건 쓰기와 배치 작업의 최종 결과를 최근 500건까지 안전하게 보관하고 필터링하는 화면을 연결했습니다.
- 개발자용 API 모니터를 추가해 모든 공통 HTTP 호출과 429 재시도 시도를 메타데이터만으로 실시간 집계합니다.
- 저장된 연결 또는 snapshot은 검증 signature가 현재 값과 일치할 때만 앱 시작 시 활성 환경으로 복원합니다.
- 연결 테스트, 프로젝트/트래커 조회, Excel 미리보기, 매핑 준비, 검증은 `BackgroundTask` 기반으로 실행하고 작업 중 로딩 오버레이와 대기 커서를 표시합니다.
- 설정, 프로젝트, 파일, 검증 단계는 필수 입력이나 선행 작업이 완료되기 전까지 `다음` 버튼을 비활성화합니다.
- 파일 단계는 값이 바뀔 때마다 Excel 을 다시 열지 않고, 사용자가 `데이터 불러오기`를 눌렀을 때만 미리보기를 갱신합니다.
- 다중 파일 업로드 시 tracker item query 대상 값은 전체 파일에서 중복 제거 후 한 번만 사전 조회해 캐시에 올립니다.
- 테스트 모드에서는 실제 업로드를 막고 Dry Run만 허용합니다.
- 기본 창 크기는 `1160x780`, 최소 크기는 `860x620`이며, 페이지 내용이 길면 내부 스크롤을 사용하고 창 높이는 화면 높이의 88%를 넘지 않도록 제한합니다.
- 알림은 커스텀 다이얼로그로 표시하며, 테마와 톤을 맞춘 상태로 오류/안내를 구분합니다.
- `QComboBox` 는 기본 시스템 화살표 대신 커스텀 chevron 아이콘을 사용합니다.

## 프로젝트 구조

- `gui_main.py`: 현재 기본 GUI 실행 경로
- `cli_main.py`: 유지보수와 보조 실행용 대화형 CLI
- `main.py`: 과거 엔트리 포인트, 현재 비권장
- `src/codebeamer_client.py`: Codebeamer REST API 클라이언트
- `src/api_monitor.py`: 최근 API 호출 메타데이터의 thread-safe 메모리 버퍼와 통계
- `src/excel_reader.py`: Excel 파일을 raw DataFrame으로 읽는 입력 계층
- `src/hierarchy_processor.py`: raw DataFrame을 merged/hierarchy/upload DataFrame으로 후처리
- `src/excel_processor.py`: 기존 import 호환용 통합 래퍼
- `src/cli_excel_utils.py`: 기존 CLI Excel helper import 호환 래퍼
- `src/upload_policy.py`: create/update/upsert 모드, 작업 범위, 루트 허용 여부, 공통 검증 상태 정책
- `src/mapping_service.py`: schema 해석용 façade
  내부 구현은 `src/mapping_reference.py`, `src/mapping_schema.py`, `src/mapping_option.py` 로 분리
- `src/wizard.py`: 업로드 오케스트레이션 façade
  내부 구현은 데이터, lookup, option 해석, create/update payload, payload cache, 실행 서비스로 분리
- `src/models/`: reference, field value, tracker item, user info, wizard state 모델
- `src/gui/`: PySide6 기반 앱 셸, 단계형 배치 GUI, 서비스 계층, upload worker
  `main_window.py`는 최상위 작업 영역을 전환하고 `batch_window.py`는 기존 9단계 마법사를 보존하며, 세부 구현은 `page_*`, `window_*`, `service_*` 모듈로 분리
- `data/gui-offline-sample/`: GUI 테스트 모드용 snapshot, 다중 Excel 샘플, 사용 안내
- `docs/`: 사용 가이드와 아키텍처 문서

호환 wrapper의 유지·제거 기준은 [호환 경로 감사](./docs/compatibility.md)에 정리되어 있습니다.
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
9. `TrackerItemChoiceField` 는 configuration 에 source tracker 정보가 있으면 이름/summary query lookup 을, 없으면 정규식 ID 추출을 사용합니다.
10. GUI 상단 데이터 설정이 켜져 있으면 파일별 루트 parent item payload 를 먼저 준비합니다.
11. row별 payload를 먼저 cache하고 preview와 upload가 같은 payload를 재사용합니다.
12. 다중 파일 업로드 시 tracker item query 값은 전체 파일 기준으로 중복 제거 후 사전 조회합니다.
13. 업로드 시점에는 파일별 루트 parent item을 먼저 만들고, 이후 child row 의 `parentItemId` 를 `created_map[parent_row_id]` 또는 루트 item 기준으로 결정합니다.
14. `Status` 는 transition 기반 후처리로 옮겨야 하므로 현재 TODO 로 남겨두고 있습니다.
15. 실행 결과와 중간 dataframe, schema, payload cache, 검증 결과를 `output/`에 저장할 수 있습니다.

## 문서

- [문서 허브](./docs/index.md)
- [아키텍처](./docs/architecture.md)
- [Codebeamer 업로드 조사 정리](./docs/codebeamer-upload-reference.md)
- [Codebeamer 프로젝트 시작 패키지](./docs/codebeamer-project-start-kit.md)
- [CLI 사용 가이드](./docs/cli-guide.md)
- [GUI 사용 가이드](./docs/gui-plan.md)
- [Codebeamer API 모니터](./docs/api-monitor.md)
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
- `TrackerItemChoiceField` 는 tracker configuration 의 `fields` 목록에서 `referenceId == schema.field_id` 로 우선 매칭하고, source tracker가 확인되면 query lookup 을 사용할 수 있습니다.
- 위 source tracker를 찾지 못하거나 offline snapshot 만 사용하는 경우에는 기본 정규식 ID 추출 방식으로 동작합니다.
- 테스트 모드에서는 실제 업로드를 막고 Dry Run만 허용합니다.
- `Status` 는 workflow transition 제약을 반영해야 하므로 현재 TODO 입니다.
- `save_state()`는 `payload_df.csv`, `payload_preview.jsonl`을 포함해 payload cache 상태도 함께 저장합니다.
