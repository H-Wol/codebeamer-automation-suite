Codebeamer Automation Suite - Windows Portable
================================================

1. ZIP 파일 전체를 로컬 폴더에 압축 해제합니다.
2. CodebeamerAutomationSuite.exe를 실행합니다.
3. 처음 실행할 때 Windows SmartScreen 경고가 표시될 수 있습니다.
   이 배포 파일은 코드 서명되지 않았으므로, SHA256SUMS.txt와 GitHub
   provenance attestation을 확인한 뒤 실행하십시오.

주의 사항
---------
- EXE와 _internal 폴더를 분리하거나 _internal 내부 파일을 이동하지 마십시오.
- .xlsx 파일은 Microsoft Excel 설치 없이 사용할 수 있습니다.
- .xls 같은 구형 Excel 형식은 Windows용 Microsoft Excel 설치가 필요합니다.
- sample 폴더에는 익명화한 오프라인 예제만 포함되어 있습니다.
- 연결 설정과 자격증명은 배포 ZIP에 포함되지 않습니다.

버전 확인
---------
명령 프롬프트 또는 PowerShell에서 다음 명령을 실행합니다.

  .\CodebeamerAutomationSuite.exe --version

정상 동작 확인
-------------

  .\CodebeamerAutomationSuite.exe --smoke-test
