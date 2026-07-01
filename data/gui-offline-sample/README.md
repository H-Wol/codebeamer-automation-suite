# GUI 오프라인 테스트용 예시 데이터

이 폴더는 GUI `테스트 모드`를 서버 없이 검증할 때 바로 사용할 수 있는 샘플 세트입니다.

포함 파일:

- `offline_schema.json`
  - 오프라인 트래커 schema snapshot
- `offline_tracker_configuration.json`
  - `TrackerItemChoiceField` source tracker 정보를 포함한 tracker configuration snapshot
- `files/SAMPLE_MODULE_A_TC_001.xlsx`
  - 정상 Dry Run 예시 1
- `files/SAMPLE_MODULE_B_TC_002.xlsx`
  - 정상 Dry Run 예시 2
- `files/SAMPLE_LOOKUP_TC_003.xlsx`
  - lookup 실패와 검증 이슈를 의도적으로 보여주는 예시

권장 빠른 테스트 순서:

1. GUI 실행 후 설정 화면에서 `테스트` 토글을 켭니다.
2. `Schema Snapshot`에 `data/gui-offline-sample/offline_schema.json`을 선택합니다.
3. `Config Snapshot`에 `data/gui-offline-sample/offline_tracker_configuration.json`을 선택합니다.
4. 프로젝트 단계로 이동하면 테스트 프로젝트와 트래커가 자동으로 채워집니다.
5. 파일 단계에서 `SAMPLE_MODULE_A_TC_001.xlsx`, `SAMPLE_MODULE_B_TC_002.xlsx`를 함께 선택합니다.
6. 아래 값으로 맞춘 뒤 `데이터 불러오기`를 누릅니다.
   - `Sheet Name`: `Upload`
   - `Header Row`: `1`
   - `Summary Column`: `Summary`
7. 첫 Dry Run에서는 아래 컬럼 위주로 매핑하면 서버 lookup 없이 끝까지 확인할 수 있습니다.
   - `Summary`
   - `Description`
   - `Priority`
   - `Approved`
   - `Verification Stage`
   - `Test Steps.Action`
   - `Test Steps.Expected result`
   - `Test Steps.Critical`
   - `Related Requirement`
8. `Related Requirement`는 테스트 모드에서 query lookup이 아니라 기본 regex ID 추출 방식으로 두는 편이 맞습니다.
   - 샘플 값은 `[REQ:9001001]` 같은 형식이라 기본 regex로 바로 인식됩니다.
9. `Owner`, `Review Team`은 오프라인 snapshot에 사용자/그룹 디렉터리가 없으므로 첫 성공 경로에서는 매핑하지 않는 편이 맞습니다.

이슈 화면 확인용 샘플:

- `files/SAMPLE_LOOKUP_TC_003.xlsx`
  - `Owner`, `Review Team`에 실제 값이 들어 있어 lookup 실패와 차단 경고를 확인하기 좋습니다.
  - `Related Requirement`도 이름 기반 조회 예시 값이 포함되어 있어 테스트 모드에서 query 방식을 고르면 의도적으로 막히는 흐름을 볼 수 있습니다.

파일명 파싱 테스트 팁:

- 상단 데이터 summary를 파일명 전체로 쓰려면 정규식 `^(.*)\\.xlsx$` 를 사용하면 됩니다.
- 샘플 파일명은 `SAMPLE_<MODULE>_TC_<번호>.xlsx` 규칙이라 미리보기 검증에도 적합합니다.
