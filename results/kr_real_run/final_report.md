# IDEAINNOV.COM x Nemotron-Personas-KR 시뮬레이션 결과

- 제품: IDEAINNOV (https://ideainnov.com)
- 표본: 실제 NVIDIA Nemotron-Personas-KR 데이터셋에서 추출한 페르소나 25명 (batch of 25)
- 방식: 배치당 25명씩 1회 LLM 호출로 독립 판정(1차) -> 집계 -> 공론 요약을 반영해 재판정(2차)
- 실제 호출 비용 합계: **$0.2183**

### 1차 판정 (독립 판단, 서로 영향 없음)

- 사용 의향(would_use): yes **0%** / maybe 4.0% / no 96.0%
- user_type: {'not_applicable': 96.0, 'adjacent': 4.0}
- 결제 의향(would_pay): yes **0%** / only_free_tier 4.0% / no 96.0%
- 상위 거부 이유:
  - 평생 하역 노동에 종사해온 초등학교 학력의 74세로 PDE나 논문 작성과는 전혀 무관한 삶을 살고 있음 (1명)
  - 자연과학 학사이지만 회계 사무원으로 실무에 종사하며 논문 작성이나 PDE 연구와 무관한 업무를 함 (1명)
  - 고졸 학력의 무직 은퇴자로 학술 연구나 논문 제출과 전혀 관계없는 일상을 보냄 (1명)
  - 언론학 전공에 현재 무직 상태로 공학/자연과학 연구와 무관한 자격증 취득을 목표로 함 (1명)
  - 고졸 학력의 서비스직 종사자로 학술 논문 작성이나 공학 연구 업무와 무관함 (1명)
- 직업군(휴리스틱)별 user_type 분포:
  - general_service_other: {'not_applicable': 5}
  - business_admin: {'not_applicable': 5}
  - unemployed_or_retired: {'not_applicable': 8}
  - technical_trade: {'not_applicable': 3}
  - healthcare_professional: {'not_applicable': 2}
  - research_or_engineering: {'not_applicable': 1, 'adjacent': 1}

### 2차 판정 (전체 공론 요약을 인지한 뒤 재판단)

- 사용 의향(would_use): yes **0%** / maybe 4.0% / no 96.0%
- user_type: {'not_applicable': 96.0, 'adjacent': 4.0}
- 결제 의향(would_pay): yes **0%** / only_free_tier 4.0% / no 96.0%
- 상위 거부 이유:
  - 평생 하역 노동만 해온 초등학교 학력자로 PDE 연구나 논문 작성과 전혀 무관한 삶 (1명)
  - 자연과학 학사이지만 부동산 회계 사무원으로 논문·PDE 연구와 무관한 실무를 함 (1명)
  - 고졸 무직 은퇴자로 학술 연구나 논문 제출과 무관한 일상 (1명)
  - 언론학 전공 무직 주부로 공학·과학 연구와 무관한 생활 (1명)
  - 부동산 서비스직 단순 종사원으로 학술 논문 작성과 무관 (1명)
- 직업군(휴리스틱)별 user_type 분포:
  - general_service_other: {'not_applicable': 5}
  - business_admin: {'not_applicable': 5}
  - unemployed_or_retired: {'not_applicable': 8}
  - technical_trade: {'not_applicable': 3}
  - healthcare_professional: {'not_applicable': 2}
  - research_or_engineering: {'not_applicable': 1, 'adjacent': 1}

### 1차 -> 2차 의견 변화 (공론 노출 효과)

- 판정이 바뀐 페르소나: 0/25 (0.0%)
- 더 긍정적으로 변화: 0명 / 더 부정적으로 변화: 0명

### 결론 요약 (누가 쓰고 / 왜 안 쓰고 / 누가 돈을 내는가)

- **누가 쓰는가**: user_type=core_target으로 분류된 페르소나는 거의 전부 'research_or_engineering' 직업군(연구원/엔지니어/대학원 이상 학력 + 공학·IT·자연과학 전공)에 집중되어 있음 — 일반 인구 표본에서는 소수.
- **왜 안 쓰는가**: 지배적 거부 사유는 '내 직업/전공이 PDE 기반 연구·논문 작성과 무관함' — 일반 사무직·서비스직·은퇴자 페르소나 다수가 여기 해당.
- **누가 돈을 내는가**: 결제 의향은 사용 의향보다 항상 낮음 — 핵심 타깃조차 무료 체험/종량제로 먼저 검증한 뒤에만 월 구독으로 전환하려는 경향이 보임 (아래 상세 표 참고).
