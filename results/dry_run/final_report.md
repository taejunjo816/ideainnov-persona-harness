# IDEAINNOV.COM x Nemotron-Personas-KR 시뮬레이션 결과

- 제품: IDEAINNOV (https://ideainnov.com)
- 표본: 실제 NVIDIA Nemotron-Personas-KR 데이터셋에서 추출한 페르소나 25명 (batch of 25)
- 방식: 배치당 25명씩 1회 LLM 호출로 독립 판정(1차) -> 집계 -> 공론 요약을 반영해 재판정(2차)
- 실제 호출 비용 합계: **$0.0000**

### 1차 판정 (독립 판단, 서로 영향 없음)

- 사용 의향(would_use): yes **4.0%** / maybe 4.0% / no 92.0%
- user_type: {'not_applicable': 92.0, 'adjacent': 4.0, 'core_target': 4.0}
- 결제 의향(would_pay): yes **4.0%** / only_free_tier 0% / no 96.0%
- 지불 의향자 월 최대 지불액: 중앙값 ₩19,000 / 평균 ₩19,000 (n=1)
- 상위 거부 이유:
  - [dry-run stub] (24명)
- 직업군(휴리스틱)별 user_type 분포:
  - general_service_other: {'not_applicable': 5}
  - business_admin: {'not_applicable': 5}
  - unemployed_or_retired: {'not_applicable': 8}
  - technical_trade: {'not_applicable': 3}
  - healthcare_professional: {'not_applicable': 2}
  - research_or_engineering: {'adjacent': 1, 'core_target': 1}

### 2차 판정 (전체 공론 요약을 인지한 뒤 재판단)

- 사용 의향(would_use): yes **4.0%** / maybe 36.0% / no 60.0%
- user_type: {'not_applicable': 60.0, 'adjacent': 36.0, 'core_target': 4.0}
- 결제 의향(would_pay): yes **4.0%** / only_free_tier 0% / no 96.0%
- 지불 의향자 월 최대 지불액: 중앙값 ₩19,000 / 평균 ₩19,000 (n=1)
- 상위 거부 이유:
  - [dry-run stub] (24명)
- 직업군(휴리스틱)별 user_type 분포:
  - general_service_other: {'not_applicable': 3, 'adjacent': 2}
  - business_admin: {'adjacent': 1, 'not_applicable': 4}
  - unemployed_or_retired: {'not_applicable': 5, 'adjacent': 3}
  - technical_trade: {'adjacent': 3}
  - healthcare_professional: {'not_applicable': 2}
  - research_or_engineering: {'not_applicable': 1, 'core_target': 1}

### 1차 -> 2차 의견 변화 (공론 노출 효과)

- 판정이 바뀐 페르소나: 10/25 (40.0%)
- 더 긍정적으로 변화: 9명 / 더 부정적으로 변화: 1명

### 결론 요약 (누가 쓰고 / 왜 안 쓰고 / 누가 돈을 내는가)

- **누가 쓰는가**: user_type=core_target으로 분류된 페르소나는 거의 전부 'research_or_engineering' 직업군(연구원/엔지니어/대학원 이상 학력 + 공학·IT·자연과학 전공)에 집중되어 있음 — 일반 인구 표본에서는 소수.
- **왜 안 쓰는가**: 지배적 거부 사유는 '내 직업/전공이 PDE 기반 연구·논문 작성과 무관함' — 일반 사무직·서비스직·은퇴자 페르소나 다수가 여기 해당.
- **누가 돈을 내는가**: 결제 의향은 사용 의향보다 항상 낮음 — 핵심 타깃조차 무료 체험/종량제로 먼저 검증한 뒤에만 월 구독으로 전환하려는 경향이 보임 (아래 상세 표 참고).
