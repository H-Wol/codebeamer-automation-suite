# Codebeamer Automation Suite

Excel 기반 계층형 데이터를 Codebeamer Tracker Item으로 변환하고 업로드하는 자동화 도구입니다.

이 저장소는 다음 작업을 수행합니다.
- Excel 시트에서 계층형 데이터를 읽기
- Tracker Schema와 Excel 컬럼 비교
- 지원되는 Option 값을 Codebeamer 참조 형식으로 변환
- Parent-Child 순서를 보장하며 업로드
- 실행 결과와 중간 산출물 저장

## 권장 실행 경로

현재 권장 엔트리 포인트는 `v2` CLI입니다.

```bash
py -3 cli_main.py
```

`cli_main.py`에는 다음 보강이 반영되어 있습니다.
- `TableFieldValue` payload 직렬화 안정화
- option/reference 필드 감지 범위 확장
- reference lookup이 필요한 필드에 대한 명시적 경고

## 프로젝트 구조

- `cli_main.py`: 현재 권장 대화형 CLI
- `cli_main.py`: 레거시 CLI, 비교 및 참고용
- `main.py`: 과거 엔트리 포인트, 현재 비권장
- `src/codebeamer_client.py`: Codebeamer REST API 클라이언트
- `src/excel_processor.py`: Excel 파싱 및 계층 구조 생성
- `src/mapping_service.py`: 레거시 스키마/옵션 매핑 서비스
- `src/mapping_service.py`: 개선된 스키마/옵션 매핑 서비스
- `src/models/`: payload 및 상태 도메인 모델 패키지
- `src/wizard.py`: 레거시 오케스트레이션 계층
- `src/wizard.py`: 개선된 오케스트레이션 계층
- `scripts/render_uml.ps1`: UML 일괄 렌더링 스크립트
- `data/`: 분석용 샘플, schema 덤프 등 보조 자료
- `output/`: 실행 결과 산출물 저장 디렉터리

## 문서 목차

- `docs/index.md`: 문서 허브
- `docs/architecture.md`: 전체 아키텍처와 모듈 책임
- `docs/class-diagram.puml`: 클래스/의존 관계 UML
- `docs/upload-sequence.puml`: 업로드 시퀀스 UML
- `docs/cli-guide.md`: 실행 및 사용 가이드
- `docs/v2-changes.md`: v2 경로의 개선 내용
- `docs/troubleshooting.md`: 자주 발생하는 문제와 대응 방법
- `docs/render-uml.md`: PlantUML 렌더링 가이드

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

3. v2 CLI 실행

```bash
py -3 cli_main.py
```

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

## 핵심 처리 흐름

1. Codebeamer에서 프로젝트와 트래커 메타데이터 조회
2. Excel 읽기 및 멀티라인 레코드 병합
3. 들여쓰기 기반 Parent-Child 계층 생성
4. Excel 컬럼과 Tracker Schema 비교
5. 지원되는 옵션 필드 변환
6. 각 row에 대한 payload 생성
7. Parent 우선 순서로 업로드
8. 실행 결과를 `output/`에 저장

## 참고 사항

- 현재 기준으로는 `cli_main.py` 사용을 권장합니다.
- `TableField` 컬럼은 `TableFieldName.ColumnName` 형식의 Excel 헤더를 기준으로 감지합니다.
- 정적 option 목록이 없는 reference 필드는 v2에서 명시적으로 드러납니다.
