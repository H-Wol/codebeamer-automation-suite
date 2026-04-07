# 트러블슈팅

## `OPTION_SOURCE_UNAVAILABLE`

의미:
- 해당 필드가 option 또는 reference 성격을 가짐
- 하지만 schema가 정적 option 목록을 제공하지 않음
- 현재 코드 경로에는 그 reference 값을 동적으로 가져오는 resolver가 아직 없음

대응:
- 필드명과 `reference_type` 을 먼저 확인
- 당장은 해당 매핑을 제외할지 결정
- 또는 그 reference type에 대한 lookup provider를 구현

## payload preview가 reference 필드에서 실패함

가능한 원인:
- Excel에 값이 들어 있음
- 해당 필드가 `reference_lookup` 으로 분류됨
- 아직 resolver가 없음

대응:
- 해당 필드 매핑을 잠시 제외
- 또는 동적 resolution 지원 추가

## `TableField` 데이터가 업로드되지 않음

확인할 점:
- Excel 헤더가 `TableFieldName.ColumnName` 형식인지
- schema field 이름과 table column 이름이 정확히 일치하는지
- CLI 출력에서 감지된 `TableField` 컬럼으로 표시되는지

## 들여쓰기 관련 hierarchy 오류

가능한 원인:
- 인접한 논리 row 사이에서 들여쓰기 단계가 1보다 크게 점프함

대응:
- 각 row 사이 단계 증가가 최대 1이 되도록 정리
- summary 컬럼이 올바른지 다시 확인

## summary 컬럼을 찾지 못함

가능한 원인:
- 설정된 summary 컬럼명이 실제 Excel 헤더와 다름
- 잘못된 sheet 선택
- header row 설정 오류

대응:
- `EXCEL_HEADER_ROW` 확인
- 선택한 sheet 재확인
- 실제 Excel 헤더 문자열 확인

## `xlwings` 로 workbook을 열지 못함

확인할 점:
- 파일 경로가 실제로 존재하는지
- 다른 프로세스가 파일을 잠그고 있지 않은지
- 현재 환경에서 Excel 설치가 필요한지

## parent는 올라갔는데 child가 unresolved로 남음

가능한 원인:
- 상위 row가 먼저 실패해서 생성되지 않음
- child row가 필요한 parent item id를 받지 못함

대응:
- 먼저 `failed_df` 확인
- 가장 첫 번째 parent 실패 원인을 해결한 뒤 전체 배치를 다시 실행

## 저장 산출물이 혼란스러움

참고:
- 저장소에는 레거시 경로와 v2 경로가 함께 존재함
- 가능한 한 v2 CLI 경로에서 생성한 산출물을 기준으로 검토하는 것을 권장
