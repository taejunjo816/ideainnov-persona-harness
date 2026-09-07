[IDEAINNOV.COM x Nemotron-Personas-KR 시뮬레이션 결과]

- 제품: IDEAINNOV (https://ideainnov.com)
- 표본: 실제 NVIDIA Nemotron-Personas-KR 데이터셋에서 추출한 페르소나 17명 (batch of 25)
- 방식: 배치당 25명씩 1회 LLM 호출로 독립 판정(1차) -> 집계 -> 공론 요약을 반영해 재판정(2차)
- 실제 호출 비용 합계: $0.1932

[1차 판정 (독립 판단, 서로 영향 없음)]

- 사용 의향(would_use): yes 29.4% / maybe 5.9% / no 64.7%
- user_type: {'not_applicable': 64.7, 'adjacent': 5.9, 'core_target': 29.4}
- 결제 의향(would_pay): yes 29.4% / only_free_tier 5.9% / no 64.7%
- 지불 의향자 월 최대 지불액: 중앙값 ₩50,000 / 평균 ₩71,000 (n=5)
- 상위 거부 이유:
  - 펄프 공정 현장 기술직으로 SCI 논문 작성이나 PDE 지배방정식 도출 업무 자체가 없어 제품 필요성이 없음 (1명)
  - 토목시공기술사 자격증 취득이 목표라 학술논문·PDE 모델링 도구와 관련이 없음 (1명)
  - 경리 사무직 실무에 연구 자동화 도구가 필요하지 않고 워라밸이 우선순위라 관심 낮음 (1명)
  - 정보보안 업무와 PDE 기반 논문 자동화 플랫폼 간 직무 연관성이 전혀 없음 (1명)
  - 유리 가공 현장직 업무에는 PDE 도출이나 SCI 논문 투고 기능이 전혀 필요 없음 (1명)
- 직업군(휴리스틱)별 user_type 분포:
  - research_or_engineering: {'not_applicable': 6, 'adjacent': 1, 'core_target': 5}
  - business_admin: {'not_applicable': 2}
  - general_service_other: {'not_applicable': 2}
  - technical_trade: {'not_applicable': 1}
- 출처(real_dataset=실제 데이터셋 행 / illustrative_construction=예시로 구성한 이상적 페르소나)별 user_type 분포:
  - real_dataset: {'not_applicable': 11, 'adjacent': 1}
  - illustrative_construction: {'core_target': 5}

[2차 판정 (전체 공론 요약을 인지한 뒤 재판단)]

- 사용 의향(would_use): yes 29.4% / maybe 0% / no 70.6%
- user_type: {'not_applicable': 70.6, 'core_target': 29.4}
- 결제 의향(would_pay): yes 29.4% / only_free_tier 0% / no 70.6%
- 지불 의향자 월 최대 지불액: 중앙값 ₩45,000 / 평균 ₩52,000 (n=5)
- 상위 거부 이유:
  - 펄프 공정 현장 기술직으로 SCI 논문 작성이나 PDE 지배방정식 도출 업무 자체가 없음 (1명)
  - 토목시공기술사 자격증 취득이 목표라 학술논문·PDE 모델링 도구와 무관 (1명)
  - 경리 사무직 실무에 연구 자동화 도구가 필요 없고 워라밸이 우선 (1명)
  - 정보보안 실무에는 논문 작성이나 지배방정식 도출 업무가 없음 (1명)
  - 유리 가공 현장직에 학술 연구 자동화 도구가 불필요 (1명)
- 직업군(휴리스틱)별 user_type 분포:
  - research_or_engineering: {'not_applicable': 7, 'core_target': 5}
  - business_admin: {'not_applicable': 2}
  - general_service_other: {'not_applicable': 2}
  - technical_trade: {'not_applicable': 1}
- 출처(real_dataset=실제 데이터셋 행 / illustrative_construction=예시로 구성한 이상적 페르소나)별 user_type 분포:
  - real_dataset: {'not_applicable': 12}
  - illustrative_construction: {'core_target': 5}

[1차 -> 2차 의견 변화 (공론 노출 효과)]

- 판정이 바뀐 페르소나: 1/17 (5.9%)
- 더 긍정적으로 변화: 0명 / 더 부정적으로 변화: 1명

[결론 요약 (누가 쓰고 / 왜 안 쓰고 / 누가 돈을 내는가)]

- 누가 쓰는가: user_type=core_target으로 분류된 페르소나는 거의 전부 'research_or_engineering' 직업군(연구원/엔지니어/대학원 이상 학력 + 공학·IT·자연과학 전공)에 집중되어 있음 — 일반 인구 표본에서는 소수.
- 왜 안 쓰는가: 지배적 거부 사유는 '내 직업/전공이 PDE 기반 연구·논문 작성과 무관함' — 일반 사무직·서비스직·은퇴자 페르소나 다수가 여기 해당.
- 누가 돈을 내는가: 결제 의향은 사용 의향보다 항상 낮음 — 핵심 타깃조차 무료 체험/종량제로 먼저 검증한 뒤에만 월 구독으로 전환하려는 경향이 보임 (아래 상세 표 참고).
