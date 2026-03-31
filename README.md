# Codebeamer Automation Suite

Codebeamer 기반 테스트 데이터 업로드 및 검증 자동화를 위한 도구

---

## 개요

Excel 기반 테스트 데이터를 Codebeamer 트래커에 업로드하기 위한 자동화 도구

### 주요 기능
- Excel 데이터 파싱 및 구조 변환
- 들여쓰기 기반 계층 구조 생성
- Tracker Schema 기반 검증
- Option 필드 자동 매핑 및 정합성 검증
- Parent-Child 관계 유지 업로드
- 결과 및 중간 데이터 저장

---

## 설치

```bash
pip install -r requirements.txt
```

---

## 환경 설정 (.env)

CODEBEAMER_BASE_URL=https://your-codebeamer-host/cb  
CODEBEAMER_USERNAME=your_username  
CODEBEAMER_PASSWORD=your_password  

---

## 실행

```bash
python main.py
```

---

## 주의사항

- 요약 컬럼 들여쓰기 구조 필수
- Option 값은 정확히 일치해야 함
- sample_item_id 필요

---

## 향후 계획

- GUI 지원
- 테스트 자동화
- 리포트 생성
