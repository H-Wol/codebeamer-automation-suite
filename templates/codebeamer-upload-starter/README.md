# Codebeamer Upload Starter

이 디렉터리는 새 Codebeamer 업로드 프로젝트를 시작할 때 복사해서 쓰는 시작 패키지입니다.

## 중요한 원칙

- tracker schema는 실행 시점에 대상 tracker에서 가져오는 것이 기준입니다.
- `tracker-schema.json`, `tracker-schema-flat.json`, `tracker-schema-flat.csv`, `tracker-contract.json` 은 수동 작성 파일이 아니라 생성 파일입니다.
- 생성된 schema snapshot은 오프라인 테스트, 계약 비교, 구현 회귀 확인에 사용합니다.

## 수동으로 채우는 파일

- `project-context.template.json`
- `input-contract.template.json`
- `mapping.template.json`
- `lookup-policy.template.json`
- `notes.template.md`

## 생성되는 파일

- `tracker-schema.json`
- `tracker-schema-flat.json`
- `tracker-schema-flat.csv`
- `tracker-contract.json`
- `payload-preview.sample.jsonl`

## 권장 순서

1. 이 디렉터리를 새 프로젝트 작업 디렉터리로 복사합니다.
2. 대상 tracker를 정한 뒤 live schema export를 실행합니다.
3. 생성된 schema snapshot을 기준으로 입력 계약과 컬럼 매핑을 채웁니다.
4. 샘플 입력 파일 1개와 payload preview 1개를 고정합니다.
5. 그 다음 uploader 구현을 시작합니다.

## 권장 export 명령

```bash
py -3 export_tracker_contract.py --project-id <PROJECT_ID> --tracker-id <TRACKER_ID>
```
