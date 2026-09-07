[홍보 문구 진화 최적화 — 한국어(KO) 최종 리포트]

중요(정직 고지): 이 점수는 합성 페르소나(AI 시뮬레이션)가 예측한 시뮬레이션 클릭 의향이며, 실제 광고의 클릭률(CTR)이 아닙니다. 표본에 `illustrative_construction`(직접 구성한 예시) 페르소나가 섞여 있다면 그 사실도 함께 밝혀야 합니다 — 이 실행의 표본 출처는 아래 참고.

- seed: 42 (재현 가능 — 동일 seed는 동일 결과)
- 요청한 세대 수: 2 / 실제 실행된 세대 수: 2
- 종료 사유(stopped_reason): generations_reached
- 점수 가중치: yes=100.0, maybe=40.0, trust=8.0  (score = w_yes*P(yes) + w_maybe*P(maybe) + w_trust*mean(trust))
- 이 언어 트랙 호출 수: 17, 비용: $6.4135 (dry_run=False)
- 세대 0 시드의 훅 유형 구성: {'숫자형': 2, '정체성호명': 1, '호기심갭': 1, '질문형': 2, '역설·반전': 1, '부정형': 1}

[우승 문구]

- id: `gen01_ko_v2_question_table_formula` (세대 1, score=55.68)
- hook_type: None / hook_template: None
- headline: 표와 수식, 정말 안 깨질까요?
- body: 47개 형식을 오가며 변환해도 편집 가능한 OMML 수식과 표 레이아웃이 그대로 남습니다. 직접 열어 확인해 보세요.
- cta: 무료 체험 시작
- angle: 질문형-변환신뢰(범용 문서 사용자 대상)
- source_evidence: mutated by claude -p (see mutation_call.json for prompt/inputs)
- products.json evidence: []

- 판정 결과: would_click_pct={'maybe': 36.0, 'no': 48.0, 'yes': 16.0}, mean_trust=3.16, n=25

[세대별 점수 추이]

| 세대 | 개체 수 | 최고 점수 | 최고 개체 | 평균 점수 |
|---:|---:|---:|---|---:|
| 0 | 8 | 37.76 | `seed_02_ko_숫자형_형식개수` | 24.88 |
| 1 | 8 | 55.68 | `gen01_ko_v2_question_table_formula` | 39.08 |

[전체 세대 통틀어 상위 hook_phrase 5]

- 'HWPX·DOCX·PDF' (14회)
- '47개 형식 상호 변환' (8회)
- '편집 가능한 OMML 객체' (8회)
- '무료 체험 시작' (6회)
- '수식 47개' (5회)

[전체 세대 통틀어 상위 blocker 5]

- 경리 실무에 수식 47개짜리 학술 초안은 전혀 쓸 일이 없다. (1회)
- 리빙 소품 브랜드 론칭에 편집 가능한 수식 초안은 아무 도움이 안 된다. (1회)
- 기계정비산업기사 자격증 준비지 논문 초안 작성이 아니라서 실익이 없다. (1회)
- 미디어 디자인 실무에 수식·심사위원 서비스는 관련성이 없다. (1회)
- 무역 실무자라 수식 47개 논문 초안을 쓸 상황이 없다. (1회)

[최종 세대 엘리트(top-3)]

- `gen01_ko_v2_question_table_formula` [None] 표와 수식, 정말 안 깨질까요?
- `gen01_ko_v3_number_formats_price` [None] 형식 변환 47개, 호출당 2,800원
- `gen01_ko_v4_biz_beyond_paper` [None] 논문만? 사업계획서도 자동으로
