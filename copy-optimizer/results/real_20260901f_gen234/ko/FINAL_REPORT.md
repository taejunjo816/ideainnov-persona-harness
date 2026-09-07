[홍보 문구 진화 최적화 — 한국어(KO) 최종 리포트]

중요(정직 고지): 이 점수는 합성 페르소나(AI 시뮬레이션)가 예측한 시뮬레이션 클릭 의향이며, 실제 광고의 클릭률(CTR)이 아닙니다. 표본에 `illustrative_construction`(직접 구성한 예시) 페르소나가 섞여 있다면 그 사실도 함께 밝혀야 합니다 — 이 실행의 표본 출처는 아래 참고.

- seed: 43 (재현 가능 — 동일 seed는 동일 결과)
- 요청한 세대 수: 3 / 실제 실행된 세대 수: 3
- 종료 사유(stopped_reason): generations_reached
- 점수 가중치: yes=100.0, maybe=40.0, trust=8.0  (score = w_yes*P(yes) + w_maybe*P(maybe) + w_trust*mean(trust))
- 이 언어 트랙 호출 수: 21, 비용: $8.0799 (dry_run=False)
- 세대 0 시드의 훅 유형 구성: {'미분류': 3}

[우승 문구]

- id: `gen04_ko_gen04_ko_seller_product_docs` (세대 4, score=72.16)
- hook_type: None / hook_template: None
- headline: 상품 서류도 형식 걱정 없이 변환
- body: 상세 문서를 HWPX·DOCX·PDF 등 47개 형식으로 오가도 표·그림 그대로. PDF 속 그림 추출해 재삽입, ₩2,800/호출.
- cta: 무료 체험 시작
- angle: 온라인 판매 걸림돌 해소: 상품 관련 서류의 형식 변환 상황으로 업무 관련성 부여
- source_evidence: mutated by claude -p (see mutation_call.json for prompt/inputs)
- products.json evidence: []

- 판정 결과: would_click_pct={'maybe': 60.0, 'yes': 20.0, 'no': 20.0}, mean_trust=3.52, n=25

[세대별 점수 추이]

| 세대 | 개체 수 | 최고 점수 | 최고 개체 | 평균 점수 |
|---:|---:|---:|---|---:|
| 2 | 3 | 49.44 | `gen01_ko_v4_biz_beyond_paper` | 48.267 |
| 3 | 8 | 68.0 | `gen03_ko_gen02_ko_v1_convert_everyday` | 49.56 |
| 4 | 8 | 72.16 | `gen04_ko_gen04_ko_seller_product_docs` | 58.68 |

[전체 세대 통틀어 상위 hook_phrase 5]

- '표 레이아웃과 스타일 그대로' (26회)
- 'HWPX·DOCX·PDF' (21회)
- '무료 체험 시작' (19회)
- '표 레이아웃도 그대로' (16회)
- '자동 구조화' (15회)

[전체 세대 통틀어 상위 blocker 5]

- 경리 실무는 주로 엑셀·회계 프로그램이라 문서 포맷 변환 수요가 크지 않다. (1회)
- 리빙 소품 브랜드·온라인 판매업엔 수식과 표 변환 기능이 전혀 필요 없다. (1회)
- 시험 성적서는 정해진 양식이라 47개 형식 변환까지 필요할지 확신이 안 선다. (1회)
- 미디어 콘텐츠 디자인은 이미지·영상 중심이라 OMML 수식 보존이 무의미하다. (1회)
- 무역 서류는 인보이스·표 위주라 수식 보존까지는 절실하지 않다. (1회)

[최종 세대 엘리트(top-3)]

- `gen04_ko_gen04_ko_seller_product_docs` [None] 상품 서류도 형식 걱정 없이 변환
- `gen04_ko_gen04_ko_office_table_safe` [None] 매일 다루는 문서, 표 안 깨지게 변환
- `gen03_ko_gen02_ko_v3_table_image_intact` [None] 표·그림 안 깨지는 문서 변환
