# Codebeamer Automation Suite

Excel 기반 계층형 데이터를 Codebeamer Tracker Item으로 변환하고 업로드하는 자동화 도구입니다.

현재 기본 실행 경로는 `cli_main.py`이며, 예전 `v2` 경로의 개선 사항은 모두 원본 모듈에 반영되어 있습니다.

## 현재 지원하는 핵심 기능

- Excel 시트에서 계층형 데이터 읽기
- Tracker schema 조회 및 Excel 컬럼과의 자동 매핑 확인
- schema의 `multipleValues=true` 필드에 대응하는 Excel 컬럼 자동 list 처리
- 정적 option 값을 Codebeamer reference payload로 변환
- `UserReference` 필드에 대해 user info 조회 후 reference로 변환
- 사용자 lookup 결과를 프로젝트 단위 임시 캐시에 저장해 반복 요청 최소화
- `TableFieldName.ColumnName` 형식 헤더를 이용한 `TableField` 조립
- payload preview 확인
- parent-first 순서 보장 업로드
- 실행 결과와 중간 산출물 저장

## 권장 실행 명령

```bash
py -3 cli_main.py
```

## 프로젝트 구조

- `cli_main.py`: 현재 권장 대화형 CLI
- `main.py`: 과거 엔트리 포인트, 현재 비권장
- `src/codebeamer_client.py`: Codebeamer REST API 클라이언트
- `src/excel_processor.py`: Excel 파싱, 멀티라인 병합, 계층 구조 생성
- `src/mapping_service.py`: schema flattening, 컬럼 비교, option/reference 처리
- `src/wizard.py`: 업로드 오케스트레이션, preview, 업로드, 상태 저장
- `src/models/`: reference, field value, tracker item, user info, wizard state 모델
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
4. Excel 데이터를 읽고 멀티라인 레코드를 하나의 논리 row로 병합합니다.
5. 들여쓰기 기준으로 parent-child 계층을 구성합니다.
6. 정적 option 필드는 reference payload로 변환합니다.
7. `UserReference` 필드는 user info를 조회하고 결과를 캐시에 저장합니다.
8. row별 payload preview 후 parent-first 순서로 업로드합니다.
9. 실행 결과와 중간 dataframe, schema, 검증 결과를 `output/`에 저장할 수 있습니다.

## 문서

- [문서 허브](./docs/index.md)
- [아키텍처](./docs/architecture.md)
- [CLI 사용 가이드](./docs/cli-guide.md)
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
- `UserReference`는 이름 또는 이메일 기준으로 user info를 조회한 뒤 reference로 변환합니다.
