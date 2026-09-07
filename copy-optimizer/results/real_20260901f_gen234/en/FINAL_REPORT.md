[홍보 문구 진화 최적화 — English(EN) 최종 리포트]

중요(정직 고지): 이 점수는 합성 페르소나(AI 시뮬레이션)가 예측한 시뮬레이션 클릭 의향이며, 실제 광고의 클릭률(CTR)이 아닙니다. 표본에 `illustrative_construction`(직접 구성한 예시) 페르소나가 섞여 있다면 그 사실도 함께 밝혀야 합니다 — 이 실행의 표본 출처는 아래 참고.

- seed: 43 (재현 가능 — 동일 seed는 동일 결과)
- 요청한 세대 수: 3 / 실제 실행된 세대 수: 3
- 종료 사유(stopped_reason): generations_reached
- 점수 가중치: yes=100.0, maybe=40.0, trust=8.0  (score = w_yes*P(yes) + w_maybe*P(maybe) + w_trust*mean(trust))
- 이 언어 트랙 호출 수: 21, 비용: $6.5687 (dry_run=False)
- 세대 0 시드의 훅 유형 구성: {'역설·반전': 1, '미분류': 1, '부정형': 1}

[우승 문구]

- id: `gen03_en_var_05_proposal_scaling` (세대 4, score=43.84)
- hook_type: None / hook_template: None
- headline: One proposal, many deliverables
- body: One proposal scales into patent planning, specs, and an IR pitch deck, backed by economic and legal analysis.
- cta: Start free
- angle: Proposal-to-deliverables scaling for business professionals (widens audience beyond paper writers)
- source_evidence: mutated by claude -p (see mutation_call.json for prompt/inputs)
- products.json evidence: []

- 판정 결과: would_click_pct={'maybe': 40.0, 'no': 52.0, 'yes': 8.0}, mean_trust=2.48, n=25

[세대별 점수 추이]

| 세대 | 개체 수 | 최고 점수 | 최고 개체 | 평균 점수 |
|---:|---:|---:|---|---:|
| 2 | 3 | 38.88 | `gen01_en_var_02_equation_preserve` | 34.507 |
| 3 | 8 | 40.32 | `gen03_en_var_05_proposal_scaling` | 30.86 |
| 4 | 8 | 43.84 | `gen03_en_var_05_proposal_scaling` | 32.24 |

[전체 세대 통틀어 상위 hook_phrase 5]

- 'Automated' (20회)
- 'KPI rationale' (14회)
- 'nothing to fix afterward' (13회)
- 'Equations stay editable objects after conversion' (12회)
- 'economic and legal analysis' (11회)

[전체 세대 통틀어 상위 blocker 5]

- A transportation attendant has no documents with equations to convert. (2회)
- The copy never says what is being matched, so its relevance to her operations work is unclear. (1회)
- A ToS-safe automated matching tool has nothing to do with her transportation attendant work or community hobbies. (1회)
- It never names what gets matched or submitted, so the STEM tinkerer can't tell if it's useful or a spammy bot. (1회)
- Automated submission matching is irrelevant to a semi-retired nurse focused on palliative care and gardening. (1회)

[최종 세대 엘리트(top-3)]

- `gen03_en_var_05_proposal_scaling` [None] One proposal, many deliverables
- `gen04_en_gen04_en_var_01_rfp_business` [None] One RFP upload, ready to pitch
- `gen04_en_gen04_en_var_02_proposal_scaling` [None] One proposal, many deliverables
