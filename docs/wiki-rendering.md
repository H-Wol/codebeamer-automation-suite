# Wiki 형식 조회 렌더링

## 목적

트래커 작업공간은 Codebeamer가 Wiki 형식으로 선언한 설명과 필드만 안전한 rich text로 표시합니다.
값에 `%%(...)` 문자열이 포함됐다는 이유만으로 형식을 추측하지 않습니다.

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
- 일반 Wiki custom field는 필드 표에서 rich text로 표시하고 원문을 tooltip과 원본 JSON에 유지합니다.
- `TableField`는 필드 표에 `행 × 열 · 열어보기` 버튼을 표시합니다.
- 테이블 보기 창은 실제 행·열 구조를 유지하며 Wiki로 선언된 셀만 렌더링합니다.
- 테이블 보기 창에서도 전체 셀을 Wiki 원문과 렌더링 보기로 전환할 수 있습니다.

## 현재 지원 문법

- `%%(color:red;font-style:italic)내용%%` 형태의 스타일 블록
- `%%red 내용%%` 형태의 기본 이름 색상
- `__굵게__`, `''기울임''`, `{{고정폭}}`
- 줄바꿈
- 대체 종료 기호 `%!`

허용하는 CSS 속성은 `color`, `background-color`, `font-size`, `font-style`, `font-weight`,
`text-decoration`으로 제한합니다. 현재 테마와 충돌하는 검정·흰색 전경색은 제거하고 화면 기본 전경색을
사용합니다.

## 보안과 제한

- 원문 HTML은 먼저 escape하며 script나 임의 HTML을 실행하지 않습니다.
- `url(...)`, `expression`, `javascript` 같은 위험한 CSS 값과 허용 목록 밖의 속성은 버립니다.
- Codebeamer plugin, 첨부 이미지, 내부 artifact link와 복합 Wiki table은 로컬에서 실행하거나 자동 조회하지 않습니다.
- 지원하지 않는 문법은 원문 보기 또는 마스킹된 원본 JSON에서 확인합니다.

Codebeamer의 전체 Wiki 엔진을 복제하는 기능이 아니라, 조회 화면에서 자주 사용되는 텍스트 스타일을 안전하게
읽기 위한 제한된 렌더러입니다.
