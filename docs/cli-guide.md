# CLI 사용 가이드

## 권장 실행 명령

```bash
py -3 cli_main.py
```

## 왜 v2를 권장하나

v2 경로에는 다음 개선이 들어 있습니다.
- `TableFieldValue` payload 직렬화 안정화
- option/reference 필드 감지 범위 확장
- reference lookup 필요 필드에 대한 명시적 경고와 실패 처리

## 요구 사항

- Python 3
- 환경에 따라 `xlwings` 가 요구하는 Excel 설치
- 대상 Codebeamer 서버 접근 네트워크
- 올바르게 설정된 `.env`

## 설치

```bash
pip install -r requirements.txt
```

## 환경 변수

필수:
- `CODEBEAMER_BASE_URL`
- `CODEBEAMER_USERNAME`
- `CODEBEAMER_PASSWORD`

선택:
- `DEFAULT_PROJECT_ID`
- `DEFAULT_TRACKER_ID`
- `EXCEL_HEADER_ROW`
- `EXCEL_SHEET_NAME`
- `LOG_LEVEL`
- `OUTPUT_DIR`

예시:

```env
CODEBEAMER_BASE_URL=https://your-codebeamer-host/cb
CODEBEAMER_USERNAME=your_username
CODEBEAMER_PASSWORD=your_password
EXCEL_HEADER_ROW=1
EXCEL_SHEET_NAME=0
LOG_LEVEL=INFO
OUTPUT_DIR=output
```

## 기대하는 Excel 형식

CLI는 다음 구조를 전제로 합니다.
- 하나의 summary 컬럼이 논리 레코드의 제목 역할을 함
- summary 셀의 들여쓰기로 계층 표현
- 여러 물리적 행이 하나의 논리 레코드를 표현할 수 있음
- list처럼 취급할 컬럼은 실행 중 선택 가능
- `TableField` 는 `TableFieldName.ColumnName` 형식 헤더 사용

## 인터랙티브 흐름

1. project 선택
2. tracker 선택
3. Excel 파일 및 sheet 선택
4. summary 컬럼 자동 감지 또는 수동 선택
5. list 컬럼 선택
6. Excel과 schema의 자동 매핑 확인
7. option/reference 필드 검증 결과 확인
8. payload preview 확인
9. dry-run 또는 실제 업로드 수행
10. 실행 결과 저장 여부 선택

## 산출물

wizard는 다음 결과를 저장할 수 있습니다.
- upload dataframe 스냅샷
- schema dataframe 스냅샷
- option 검증 결과
- success, failure, unresolved row 목록
- 생성된 item id 매핑

## 레거시 엔트리 포인트

- `cli_main.py`: 레거시 CLI, 참고용
- `main.py`: 과거 엔트리 포인트, 현재 비권장
