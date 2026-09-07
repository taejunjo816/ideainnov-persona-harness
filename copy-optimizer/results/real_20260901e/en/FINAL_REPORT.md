[홍보 문구 진화 최적화 — English(EN) 최종 리포트]

중요(정직 고지): 이 점수는 합성 페르소나(AI 시뮬레이션)가 예측한 시뮬레이션 클릭 의향이며, 실제 광고의 클릭률(CTR)이 아닙니다. 표본에 `illustrative_construction`(직접 구성한 예시) 페르소나가 섞여 있다면 그 사실도 함께 밝혀야 합니다 — 이 실행의 표본 출처는 아래 참고.

- seed: 42 (재현 가능 — 동일 seed는 동일 결과)
- 요청한 세대 수: 2 / 실제 실행된 세대 수: 2
- 종료 사유(stopped_reason): generations_reached
- 점수 가중치: yes=100.0, maybe=40.0, trust=8.0  (score = w_yes*P(yes) + w_maybe*P(maybe) + w_trust*mean(trust))
- 이 언어 트랙 호출 수: 17, 비용: $5.3856 (dry_run=False)
- 세대 0 시드의 훅 유형 구성: {'정체성호명': 1, '숫자형': 2, '호기심갭': 1, '질문형': 2, '역설·반전': 1, '부정형': 1}

[우승 문구]

- id: `seed_16_en_부정형_equation_preserve` (세대 0, score=37.12)
- hook_type: 부정형 / hook_template: 부정 명령('~하지 마세요') + 이유
- headline: Don't let your equations become images
- body: Equations stay editable objects after conversion, never flattened into images - nothing to fix afterward.
- cta: Start free now
- angle: 부정형-equation_preserve
- source_evidence: youtube_hooks.json[en]: 훅유형 '부정형' 가중 비중 0.0 views/day (share_pct_by_views 기준 apportion) -> 구조 템플릿 '부정 명령('~하지 마세요') + 이유' 적용
- products.json evidence: ['programs.hwp.differentiators_en[1]', 'programs.hwp.differentiators_en[0]']

- 판정 결과: would_click_pct={'no': 76.0, 'maybe': 24.0}, mean_trust=3.44, n=25

[세대별 점수 추이]

| 세대 | 개체 수 | 최고 점수 | 최고 개체 | 평균 점수 |
|---:|---:|---:|---|---:|
| 0 | 8 | 37.12 | `seed_16_en_부정형_equation_preserve` | 24.96 |
| 1 | 8 | 35.2 | `seed_13_en_역설_반전_tos_safe` | 28.62 |

[전체 세대 통틀어 상위 hook_phrase 5]

- 'Automated' (15회)
- '47 editable equations' (12회)
- '47 formats' (10회)
- 'DOCX, PDF' (9회)
- 'nothing to fix afterward' (7회)

[전체 세대 통틀어 상위 blocker 5]

- She is an operations specialist with an arts background, not a grad student or researcher writing papers with equations. (1회)
- A transportation attendant with some college has no need for a research-paper reviewer tool. (1회)
- He is a retail salesperson, not a grad student or researcher, so the academic tool doesn't fit him. (1회)
- A bedside nurse writing a caregiver guidebook doesn't need Q1 review or editable equations. (1회)
- She is an accountant pursuing a CPA, not writing academic research papers. (1회)

[최종 세대 엘리트(top-3)]

- `seed_13_en_역설_반전_tos_safe` [역설·반전] Automated - except the last click
- `gen01_en_var_02_equation_preserve` [None] Don't let equations become images
- `seed_16_en_부정형_equation_preserve` [부정형] Don't let your equations become images
