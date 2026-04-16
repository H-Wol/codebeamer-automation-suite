# GUI 설계 초안

## 목표

이 문서는 현재 CLI 업로드 파이프라인을 사용자용 GUI로 감싸기 위한 1차 설계안이다.

목표는 다음과 같다.

- 비개발자도 설정, 매핑, 검증, 업로드를 순서대로 수행할 수 있어야 한다.
- 이후 `exe` 로 배포 가능한 구조를 전제로 한다.
- 현재 CLI 로직을 최대한 재사용하되, GUI 에 필요한 상태 제어와 진행률 표시를 추가한다.
- 사용자가 잘못된 매핑이나 미지원 필드를 업로드 전에 확인할 수 있어야 한다.

## 현재 구현 상태

현재 브랜치 기준으로 1차 연결이 완료된 항목은 아래와 같다.

- 설정 화면
  - 설정 불러오기/저장
  - 비밀번호 저장 체크박스
  - 암호화 저장
  - 연결 테스트
  - 프로젝트/트래커 조회
- 파일 선택 화면
  - 실제 Excel 파일 선택
  - 시트 목록 조회
  - 헤더/미리보기 조회
  - Summary 컬럼 자동 제안
- 컬럼 매핑 화면
  - 업로드 대상 컬럼 표시
  - `id`, `parent` 제외
  - 체크박스/콤보박스 기반 매핑
  - 검증 실행 연결
- 검증 화면
  - `comparison_df`, `option_check_df`, `payload_df` 실패 정보 표시
- 업로드 화면
  - worker 기반 업로드 실행
  - progress 갱신
  - pause / resume / cancel 플래그 처리
  - 로그와 실패 응답 JSON 표시
- 결과 화면
  - 성공 / 실패 / 미해결 결과 테이블 표시

아직 남아 있는 항목은 다음과 같다.

- 매핑 화면의 사용성 개선
- 결과 화면에서 행 선택 기반 상세 보기 개선
- GUI 수동 테스트 및 예외 경로 보강
- `PyInstaller` 기반 exe 배포 스크립트 정리

## 권장 기술 선택

- GUI 프레임워크: `PySide6`
- 화면 전환: `QMainWindow + QStackedWidget`
- 백그라운드 실행: `QThread` 또는 `QRunnable + QThreadPool`
- 결과 테이블: `QTableView + custom table model`
- 설정 저장: JSON 파일
- 배포: `PyInstaller`

선택 이유:

- 단계형 화면과 테이블 기반 검증 결과를 구현하기 쉽다.
- 업로드 중 진행률, 일시정지, 중단을 UI thread 와 분리해 처리할 수 있다.
- 추후 `exe` 배포 시 비교적 안정적인 선택지다.

## 사용자 흐름

1. 설정 화면에서 접속 정보와 기본 옵션을 수정하거나 저장한다.
2. 파일 선택 화면에서 Excel 파일, 시트, 헤더 행을 지정한다.
3. 컬럼 매핑 화면에서 업로드 대상 컬럼과 Codebeamer 필드를 매핑한다.
4. 검증 화면에서 매핑 결과, lookup 결과, 미지원 필드를 확인한다.
5. 업로드 화면에서 진행률을 보며 실행하고, 필요 시 일시정지하거나 재개한다.
6. 결과 화면에서 성공/실패 목록과 서버 응답 JSON 을 확인하고 결과 파일을 저장한다.

각 단계는 `이전` / `다음` 버튼으로 이동한다. 페이지에 진입할 때 필요한 데이터와 UI 만 생성하거나 갱신한다.

## 화면 구성

### 1. 설정 화면

사용자가 수정할 수 있어야 하는 항목:

- `Codebeamer Base URL`
- `Username`
- `Password`
- `Default Project ID`
- `Default Tracker ID`
- `Excel Header Row`
- `Summary Column`
- `Rate Limit Retry Delay`
- `Rate Limit Max Retries`
- `Output Directory`

버튼:

- `불러오기`
- `저장`
- `기본값 복원`
- `연결 테스트`
- `다음`

요구사항:

- 설정 파일을 직접 수정하지 않아도 GUI 에서 변경 및 저장 가능해야 한다.
- 비밀번호 저장은 별도 체크박스로 제어하는 것이 안전하다.
- 최소한 최근 사용 설정 1개는 다시 불러올 수 있어야 한다.

### 2. 파일 선택 화면

사용자가 지정할 수 있어야 하는 항목:

- Excel 파일 경로
- 시트 이름 또는 시트 번호
- 헤더 행
- Summary 컬럼

UI 요소:

- 파일 선택 버튼
- 시트 선택 콤보박스
- 미리보기 테이블
- 자동 감지 결과 표시

자동 처리:

- `Summary` 를 우선 기본 컬럼으로 선택한다.
- 없으면 `요약` 을 fallback 으로 사용한다.

### 3. 컬럼 매핑 화면

이 화면은 수동 텍스트 입력보다 체크박스와 콤보박스 중심으로 구성한다.

권장 테이블 컬럼:

- `사용` 체크박스
- `Excel 컬럼명`
- `Codebeamer 필드` 콤보박스
- `필드 타입`
- `다중값 여부`
- `lookup 필요`
- `지원 여부`
- `메모`

동작 원칙:

- 자동 매핑 결과를 먼저 제안한다.
- 사용자는 체크박스로 업로드에 포함할 컬럼만 선택한다.
- 선택된 컬럼만 대상 필드 콤보박스를 활성화한다.

매핑에서 제외할 필드:

- `id`
- `parent`

제외 이유:

- `parent` 는 hierarchy processor 가 자동 계산한다.
- `id` 는 신규 업로드 매핑 대상이 아니다.

자동 계산으로 유지할 항목:

- `multipleValues=true` 여부
- payload target kind
- preconstruction kind
- lookup target kind

이 항목들은 사용자 수정 대상이 아니라 설명용 정보로 노출하는 것이 맞다.

### 4. 검증 화면

이 화면은 업로드 전 품질 게이트 역할을 한다.

표시해야 하는 항목:

- 필수 필드 누락
- unsupported field
- lookup 실패
- ambiguous lookup
- tracker item ID parse 실패
- status transition TODO 경고

권장 상단 요약:

- 전체 행 수
- 업로드 가능 행 수
- 오류 행 수
- 경고 행 수

권장 하단 테이블 컬럼:

- `행 번호`
- `컬럼명`
- `원본 값`
- `해석 결과`
- `상태`
- `오류/경고 메시지`

필터:

- `오류만 보기`
- `경고만 보기`
- `현재 선택 컬럼만 보기`

### 5. 업로드 화면

필수 요소:

- 전체 progress bar
- 현재 처리 중 행 번호 / 항목명
- 성공 수
- 실패 수
- 재시도 수
- 최근 로그 영역
- `시작`
- `일시정지`
- `재개`
- `중단`

중요 요구사항:

- 업로드는 중간에 일시정지 가능해야 한다.
- 진행률은 행 기준으로 표시한다.
- 실패 시 서버 응답 JSON 을 즉시 확인할 수 있어야 한다.

pause/resume 정책:

- 현재 진행 중인 HTTP 요청을 강제 중단하지 않는다.
- 각 row 처리 경계에서 `pause flag` 를 확인해 다음 row 로 넘어가기 전에 멈춘다.
- `cancel flag` 는 다음 안전 지점에서 종료한다.

### 6. 결과 화면

표시해야 하는 항목:

- 성공 목록
- 실패 목록
- unresolved 목록
- 실패 응답 JSON 상세
- 생성된 item ID 매핑

버튼:

- `실패 목록 내보내기`
- `결과 폴더 열기`
- `새 업로드 시작`
- `설정으로 돌아가기`

## 상태 모델

GUI 전용 상태는 최소한 아래처럼 분리한다.

### AppSettingsState

- base_url
- username
- password
- default_project_id
- default_tracker_id
- excel_header_row
- summary_column
- rate_limit_retry_delay_seconds
- rate_limit_max_retries
- output_dir

### FileSelectionState

- file_path
- sheet_name
- header_row
- preview_df

### MappingState

- selected_project_id
- selected_tracker_id
- schema_df
- mapping_dict
- enabled_columns
- auto_list_columns

### ValidationState

- comparison_df
- option_candidates_df
- option_check_df
- converted_upload_df
- blocking_issues
- warning_issues

### UploadRunState

- is_running
- is_paused
- is_cancel_requested
- current_index
- total_count
- success_count
- failed_count
- retry_count
- current_item_name
- last_error_message
- last_error_response_json

### ResultState

- success_df
- failed_df
- unresolved_df
- created_map
- output_dir

## 기존 로직 재사용 전략

재사용 대상:

- `src/codebeamer_client.py`
- `src/excel_reader.py`
- `src/hierarchy_processor.py`
- `src/mapping_service.py`
- `src/wizard.py`
- `src/models/`

GUI 에 새로 필요한 래퍼:

- 설정 파일 I/O 서비스
- 위저드 단계별 view model
- upload worker
- progress/paused/cancelled 신호 전달 계층

즉 업로드 도메인 로직은 가능한 한 기존 `wizard` 와 `mapping_service` 에 두고, GUI 는 상태 제어와 표시 역할만 담당해야 한다.

## 업로드 실행 모델

권장 실행 단위:

- 한 row 단위로 payload upload
- row 경계에서 pause/cancel 확인
- 실패 시 `error_status_code`, `error_response_json` 를 즉시 UI 상태에 반영

권장 신호:

- `started(total_count)`
- `row_started(index, upload_name)`
- `row_succeeded(index, item_id)`
- `row_failed(index, error_status_code, error_response_json)`
- `progress_changed(current, total)`
- `paused()`
- `resumed()`
- `cancelled()`
- `finished(result_state)`

## 설정 파일 정책

GUI 에서는 설정 파일 수정과 저장이 가능해야 한다.

권장 파일 예시:

- `app_settings.json`

저장 대상:

- 접속 정보
- 기본 프로젝트/트래커
- Excel 기본 옵션
- 업로드 재시도 설정
- 마지막 사용 파일 경로

주의:

- 비밀번호 저장은 사용자 동의가 있을 때만 허용하는 것이 맞다.
- OS keyring 연동은 이후 확장 항목으로 둔다.

## MVP 범위

1차 MVP 에 포함할 항목:

- 설정 수정/저장
- 비밀번호 저장 체크박스와 암호화 저장
- 파일 선택
- 프로젝트/트래커 선택
- 체크박스 기반 컬럼 매핑
- 검증 결과 테이블
- 업로드 progress bar
- pause / resume / cancel
- 결과 화면
- 실패 응답 JSON 보기

1차 MVP 에서 제외해도 되는 항목:

- status transition 후처리 UI
- 다중 프로필 관리
- 템플릿 저장
- 최근 업로드 이력 브라우저
- 고급 시각화 대시보드

## 미결정 항목

다음 구현 전에 결정이 필요한 항목:

- 비밀번호 저장 허용 여부와 방식
- 설정 파일 저장 위치
- Excel 미리보기 최대 행 수
- 업로드 중 로그 저장 포맷
- status transition 후처리 UI 반영 시점

## 권장 다음 작업

1. 컬럼 매핑 화면의 편집 UX를 개선한다.
2. 결과 화면에서 실패 행 선택 시 상세 JSON 을 동적으로 갱신한다.
3. GUI 수동 테스트 시나리오를 문서화한다.
4. `PyInstaller` 빌드 스크립트와 배포 가이드를 추가한다.

## 화면별 위젯 목록

### 설정 화면 위젯

- `QLineEdit`: Base URL
- `QLineEdit`: Username
- `QLineEdit`: Password
- `QSpinBox` 또는 `QLineEdit`: Default Project ID
- `QSpinBox` 또는 `QLineEdit`: Default Tracker ID
- `QSpinBox`: Excel Header Row
- `QLineEdit`: Summary Column
- `QDoubleSpinBox`: Rate Limit Retry Delay
- `QSpinBox`: Rate Limit Max Retries
- `QLineEdit`: Output Directory
- `QCheckBox`: 비밀번호 저장
- `QPushButton`: 불러오기
- `QPushButton`: 저장
- `QPushButton`: 기본값 복원
- `QPushButton`: 연결 테스트
- `QPushButton`: 다음

### 파일 선택 화면 위젯

- `QLineEdit`: 파일 경로
- `QPushButton`: 파일 선택
- `QComboBox`: 시트 선택
- `QSpinBox`: 헤더 행
- `QComboBox`: Summary 컬럼 선택
- `QTableView`: Excel 미리보기
- `QLabel`: 자동 감지 결과
- `QPushButton`: 이전
- `QPushButton`: 다음

### 컬럼 매핑 화면 위젯

- `QTableView`: 매핑 테이블
- `QCheckBox`: 미지원 필드 숨기기
- `QCheckBox`: 매핑된 항목만 보기
- `QPushButton`: 자동 매핑 재실행
- `QPushButton`: 선택 초기화
- `QPushButton`: 이전
- `QPushButton`: 다음

매핑 테이블 delegate:

- `사용`: 체크박스 delegate
- `Codebeamer 필드`: 콤보박스 delegate
- `메모`: 읽기 전용 텍스트

### 검증 화면 위젯

- `QLabel`: 전체 행 수
- `QLabel`: 업로드 가능 행 수
- `QLabel`: 오류 행 수
- `QLabel`: 경고 행 수
- `QCheckBox`: 오류만 보기
- `QCheckBox`: 경고만 보기
- `QCheckBox`: 현재 선택 컬럼만 보기
- `QTableView`: 검증 결과 테이블
- `QPlainTextEdit`: 상세 메시지 뷰어
- `QPushButton`: 이전
- `QPushButton`: 다음

### 업로드 화면 위젯

- `QProgressBar`: 전체 진행률
- `QLabel`: 현재 처리 중 항목
- `QLabel`: 성공 수
- `QLabel`: 실패 수
- `QLabel`: 재시도 수
- `QLabel`: 현재 상태
- `QPlainTextEdit`: 실시간 로그
- `QPlainTextEdit`: 최근 실패 응답 JSON
- `QPushButton`: 시작
- `QPushButton`: 일시정지
- `QPushButton`: 재개
- `QPushButton`: 중단
- `QPushButton`: 결과 화면으로 이동

### 결과 화면 위젯

- `QTabWidget`
  - 성공 목록 탭
  - 실패 목록 탭
  - unresolved 목록 탭
  - 생성 ID 매핑 탭
- `QTableView`: 각 결과 테이블
- `QPlainTextEdit`: 실패 응답 JSON 상세 뷰
- `QPushButton`: 실패 목록 내보내기
- `QPushButton`: 결과 폴더 열기
- `QPushButton`: 새 업로드 시작
- `QPushButton`: 설정으로 돌아가기

## 버튼 동작 정의

### 설정 화면

- `불러오기`
  - 저장된 GUI 설정 파일을 읽는다.
  - 유효하지 않은 값이 있으면 필드 단위 오류를 표시한다.
- `저장`
  - 현재 입력값을 검증한 뒤 설정 파일에 저장한다.
  - 저장 성공 시 상태 표시줄에 메시지를 남긴다.
- `기본값 복원`
  - GUI 기본값으로 되돌린다.
- `연결 테스트`
  - Base URL, Username, Password 로 API 연결 여부를 확인한다.
  - 성공 시 프로젝트 조회 가능 상태로 전환한다.
- `다음`
  - 필수 설정값 검증 후 파일 선택 화면으로 이동한다.

### 파일 선택 화면

- `파일 선택`
  - 파일 다이얼로그를 열고 Excel 파일 경로를 채운다.
  - 파일이 바뀌면 시트 목록과 미리보기를 다시 불러온다.
- `이전`
  - 설정 화면으로 돌아간다.
- `다음`
  - 파일, 시트, 헤더 행 검증 후 컬럼 매핑 화면으로 이동한다.

### 컬럼 매핑 화면

- `자동 매핑 재실행`
  - 현재 schema 기준으로 Excel 컬럼 자동 매핑을 다시 계산한다.
- `선택 초기화`
  - 사용 체크박스와 수동 지정 필드를 초기 상태로 되돌린다.
- `이전`
  - 파일 선택 화면으로 돌아간다.
- `다음`
  - 최소 필수 매핑 충족 여부를 확인한 뒤 검증 화면으로 이동한다.

### 검증 화면

- `이전`
  - 컬럼 매핑 화면으로 돌아가 수정한다.
- `다음`
  - blocking issue 가 없을 때만 업로드 화면으로 이동한다.
  - blocking issue 가 있으면 이동을 차단하고 해당 건수를 강조한다.

### 업로드 화면

- `시작`
  - upload worker 를 시작한다.
  - 시작 후 설정/매핑 관련 화면 이동은 잠근다.
- `일시정지`
  - pause flag 를 true 로 변경한다.
  - 현재 row 완료 후 대기 상태로 전환한다.
- `재개`
  - pause flag 를 false 로 변경하고 worker 진행을 재개한다.
- `중단`
  - cancel flag 를 true 로 변경한다.
  - 다음 안전 지점에서 종료한다.
- `결과 화면으로 이동`
  - 업로드가 완료되었거나 중단된 후에만 활성화한다.

### 결과 화면

- `실패 목록 내보내기`
  - `failed_df.csv`, `failed_responses.jsonl` 를 저장하거나 복사한다.
- `결과 폴더 열기`
  - output 디렉터리를 연다.
- `새 업로드 시작`
  - 업로드 관련 상태를 초기화하고 파일 선택 화면으로 이동한다.
- `설정으로 돌아가기`
  - 전체 세션을 닫고 설정 화면으로 이동한다.

## 상태 전이

### 페이지 전이

```text
설정
  -> 파일 선택
  -> 컬럼 매핑
  -> 검증
  -> 업로드
  -> 결과
```

세부 규칙:

- `설정 -> 파일 선택`
  - 접속 정보가 최소 조건을 만족해야 한다.
- `파일 선택 -> 컬럼 매핑`
  - 파일, 시트, 헤더 행이 유효해야 한다.
- `컬럼 매핑 -> 검증`
  - 필수 컬럼 매핑이 완료되어야 한다.
- `검증 -> 업로드`
  - blocking issue 가 없어야 한다.
- `업로드 -> 결과`
  - 완료 또는 중단 상태여야 한다.

### 업로드 상태 전이

```text
idle
  -> running
  -> paused
  -> running
  -> completed

idle
  -> running
  -> cancelling
  -> cancelled

idle
  -> running
  -> failed
```

설명:

- `idle`
  - 업로드 전 초기 상태
- `running`
  - worker 가 row 를 순차 처리 중인 상태
- `paused`
  - 현재 row 완료 후 다음 row 시작 전 대기 상태
- `cancelling`
  - 중단 요청을 받았고 종료 지점으로 이동 중인 상태
- `completed`
  - 전체 row 처리 완료
- `cancelled`
  - 사용자 요청으로 종료
- `failed`
  - worker 수준 치명적 오류 발생

## 와이어프레임 초안

### 설정 화면

```text
+------------------------------------------------------+
| [설정]                                               |
| Base URL          [______________________________]   |
| Username          [______________________________]   |
| Password          [______________________________]   |
| [ ] 비밀번호 저장                                   |
| Default Project   [________]  Default Tracker [__]   |
| Header Row        [__]       Summary Column [____]   |
| Retry Delay       [__._]     Max Retries   [___]     |
| Output Dir        [________________________] [찾기]  |
|                                                      |
| [불러오기] [저장] [기본값 복원] [연결 테스트] [다음] |
+------------------------------------------------------+
```

### 컬럼 매핑 화면

```text
+----------------------------------------------------------------------------------+
| [컬럼 매핑]                                                                      |
| [ ] 미지원 필드 숨기기   [ ] 매핑된 항목만 보기   [자동 매핑 재실행] [선택 초기화] |
|----------------------------------------------------------------------------------|
| 사용 | Excel 컬럼 | Codebeamer 필드 | 타입 | 다중값 | lookup | 지원 | 메모       |
| [x] | Summary    | Summary         | text | false  | no     | yes  |            |
| [x] | 담당자      | MemberField     | ref  | true   | yes    | yes  | USER/ROLE |
| [ ] | parent     | -               | -    | -      | -      | n/a  | 제외      |
| [ ] | id         | -               | -    | -      | -      | n/a  | 제외      |
|----------------------------------------------------------------------------------|
| [이전]                                                              [다음]      |
+----------------------------------------------------------------------------------+
```

### 업로드 화면

```text
+--------------------------------------------------------------+
| [업로드]                                                     |
| 진행률: [######################------------] 62%             |
| 현재 항목: REQ-102                                            |
| 성공 120   실패 3   재시도 4   상태 running                  |
|--------------------------------------------------------------|
| 로그                                                         |
| - row 121 uploaded                                           |
| - row 122 rate limited, retry in 4s                          |
| - row 123 failed: 400                                        |
|--------------------------------------------------------------|
| 최근 실패 응답 JSON                                          |
| {                                                            |
|   "message": "Invalid tracker item"                          |
| }                                                            |
|--------------------------------------------------------------|
| [시작] [일시정지] [재개] [중단] [결과 화면으로 이동]         |
+--------------------------------------------------------------+
```

## 구현 우선순위

1. 설정 화면
2. 파일 선택 화면
3. 컬럼 매핑 화면
4. 검증 화면
5. 업로드 worker 와 progress/pause/resume
6. 결과 화면

이 순서가 맞는 이유:

- 앞단 화면이 준비되어야 기존 `wizard` 흐름을 GUI 에 연결할 수 있다.
- pause/resume 은 upload worker 구조가 잡힌 뒤 구현해야 안전하다.
- 결과 화면은 upload 상태 구조가 확정된 뒤 붙이는 것이 중복 작업이 적다.
