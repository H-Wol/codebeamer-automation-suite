# Wiki 형식 조회 렌더링

## 목적

트래커 작업공간은 Codebeamer가 Wiki 형식으로 선언한 설명과 필드만 안전한 rich text로 표시합니다.
온라인에서는 Codebeamer의 `/v3/projects/{projectId}/wiki2html`을 우선 사용하고, 테스트 모드나
서버 렌더링 실패 시 제한된 로컬 렌더러를 사용합니다. 값에 `%%(...)` 문자열이 포함됐다는 이유만으로
형식을 추측하지 않습니다.

## 형식 판정

| 대상 | Wiki 렌더링 조건 |
| --- | --- |
| 아이템 설명 | `descriptionFormat`이 `Wiki` 또는 명시적 Wiki 계열 값 |
| 일반 custom field | 응답 `type` 또는 `valueModel`이 `WikiTextField` / `WikiTextFieldValue` |
| `TableField` 셀 | 열 schema 또는 셀 응답의 `type` / `valueModel`이 Wiki 계열 |
| PlainText 또는 타입 미확인 | 렌더링하지 않고 원문 유지 |

이 규칙으로 일반 텍스트에 우연히 Wiki와 유사한 기호가 들어간 경우의 오변환을 막습니다.

## 화면 동작

- 설명은 렌더링 보기를 기본값으로 사용하고 `Wiki 원문`과 `렌더링 보기`를 전환할 수 있습니다.
- 일반 Wiki custom field는 compact `열어보기`로 표시하고 별도 큰 창에서 서버 렌더링 결과를 확인합니다.
- `TableField`는 필드 표에 `행 × 열 · 열어보기` 버튼을 표시합니다.
- 테이블 보기 창은 실제 행·열 구조를 유지하며 Wiki로 선언된 셀만 렌더링합니다.
- 열 머리글 경계를 드래그해 너비를 조정하거나 `열 너비 맞춤`으로 초기화할 수 있습니다.
- 행 번호 경계를 드래그해 높이를 조정하거나 `행 높이 맞춤`으로 복원할 수 있습니다.
  내용이 화면을 넘으면 가로·세로 스크롤을 표시합니다.
- `전체 화면`과 `창 모드` 버튼으로 테이블 팝업의 표시 모드를 전환할 수 있습니다.
- 테이블 보기 창에서도 전체 셀을 Wiki 원문과 렌더링 보기로 전환할 수 있습니다.
- TableField Wiki 셀은 보이는 순서대로 처리하며 서버 요청은 최대 4개까지만 동시에 실행합니다.
- 상세 화면의 `첨부 파일` 영역은 현재 아이템의 첨부 메타데이터를 표시하고 사용자가 선택한 파일만 저장합니다.

## 현재 지원 문법

- `%%(color:red;font-style:italic)내용%%` 형태의 스타일 블록
- `%%red 내용%%` 형태의 기본 이름 색상
- `__굵게__`, `''기울임''`, `{{고정폭}}`
- 줄바꿈
- 대체 종료 기호 `%!`
- `||` 머리글과 `|` 셀로 구성된 단순 Wiki table

온라인 서버 렌더링에서는 Codebeamer가 지원하는 고급 Table plugin 결과도 표시할 수 있습니다. 로컬
fallback은 `Table`, sortable, zebra plugin을 재구현하지 않으며 원문에서 확인해야 합니다.

## 이미지와 첨부 리소스

- 서버 HTML의 이미지 URL을 `QTextBrowser`가 직접 요청하지 않습니다.
- 현재 Codebeamer와 origin이 같고 `attachment` 또는 `displayDocument` 형태로 확인되는 URL만 기존 인증으로 조회합니다.
- 받은 이미지는 `cb-attachment://...` 내부 URL로 치환해 Qt 문서에 로컬 resource로 넣습니다.
- 외부 HTTP(S), `data:`, `file:`, `javascript:` 이미지와 확인되지 않은 같은-origin 경로는 차단합니다.
- 자동 이미지는 파일당 10MB, 선택 아이템 합계 50MB까지 허용합니다. 응답 길이와 실제 수신량을 모두 검사합니다.
- 첨부 저장은 대상 폴더의 임시 파일을 완성한 뒤 교체하므로 실패한 다운로드가 정상 파일로 남지 않습니다.

현재 공개 문서만으로 아이템 첨부 목록 endpoint와 과거 첨부 revision 해석은 확정할 수 없습니다. 구현은
`/v3/items/{itemId}/attachments` adapter와 상세 응답의 `attachments` 메타데이터를 지원하지만 대상 서버
Swagger 및 실데이터로 확인해야 합니다. Baseline 상세는 최신 첨부와 섞이지 않도록 첨부 목록과 인라인
이미지 자동 다운로드를 차단합니다.

허용하는 CSS 속성은 `color`, `background-color`, `font-size`, `font-style`, `font-weight`,
`text-decoration`으로 제한합니다. 현재 테마와 충돌하는 검정·흰색 전경색은 제거하고 화면 기본 전경색을
사용합니다.

## 보안과 제한

- 원문 HTML은 먼저 escape하며 script나 임의 HTML을 실행하지 않습니다.
- `url(...)`, `expression`, `javascript` 같은 위험한 CSS 값과 허용 목록 밖의 속성은 버립니다.
- Codebeamer plugin과 복합 Wiki table은 로컬에서 실행하지 않습니다.
- 지원하지 않는 문법은 원문 보기 또는 마스킹된 원본 JSON에서 확인합니다.
- 서버 HTML은 허용된 기본 텍스트·목록·table·링크·이미지 tag만 남기며 script, iframe, form,
  object, embed, event handler와 위험한 URL scheme을 제거합니다.

로컬 렌더러는 Codebeamer의 전체 Wiki 엔진을 복제하지 않습니다. 온라인 서버 렌더링과 안전한 로컬
fallback을 분리해 복합 문법은 서버가 해석하고 클라이언트는 HTML과 인증 리소스의 안전 경계를 담당합니다.
