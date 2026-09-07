[KO vs EN 홍보 문구 비교 리포트]

정직 고지: 두 언어 트랙은 서로 다른 페르소나 표본(KR/US)과 서로 다른 언어의 문구를 완전히 독립적으로 진화시킨 결과이며, 시뮬레이션 클릭 의향 비교이지 실측 A/B 테스트가 아닙니다.

[우승 문구 나란히 비교]

| | KO | EN |
|---|---|---|
| headline | 표와 수식, 정말 안 깨질까요? | Don't let your equations become images |
| body | 47개 형식을 오가며 변환해도 편집 가능한 OMML 수식과 표 레이아웃이 그대로 남습니다. 직접 열어 확인해 보세요. | Equations stay editable objects after conversion, never flattened into images - nothing to fix afterward. |
| cta | 무료 체험 시작 | Start free now |
| hook_type | None | 부정형 |
| score | 55.68 | 37.12 |

[언어별 상위 hook_phrase]

KO

- 'HWPX·DOCX·PDF' (14)
- '47개 형식 상호 변환' (8)
- '편집 가능한 OMML 객체' (8)
- '무료 체험 시작' (6)
- '수식 47개' (5)

EN

- 'Automated' (15)
- '47 editable equations' (12)
- '47 formats' (10)
- 'DOCX, PDF' (9)
- 'nothing to fix afterward' (7)

[언어별 상위 blocker]

KO

- 경리 실무에 수식 47개짜리 학술 초안은 전혀 쓸 일이 없다. (1)
- 리빙 소품 브랜드 론칭에 편집 가능한 수식 초안은 아무 도움이 안 된다. (1)
- 기계정비산업기사 자격증 준비지 논문 초안 작성이 아니라서 실익이 없다. (1)
- 미디어 디자인 실무에 수식·심사위원 서비스는 관련성이 없다. (1)
- 무역 실무자라 수식 47개 논문 초안을 쓸 상황이 없다. (1)

EN

- She is an operations specialist with an arts background, not a grad student or researcher writing papers with equations. (1)
- A transportation attendant with some college has no need for a research-paper reviewer tool. (1)
- He is a retail salesperson, not a grad student or researcher, so the academic tool doesn't fit him. (1)
- A bedside nurse writing a caregiver guidebook doesn't need Q1 review or editable equations. (1)
- She is an accountant pursuing a CPA, not writing academic research papers. (1)

[최종 엘리트 기준 훅 유형 비교]

- 두 언어 모두에서 최종 엘리트에 든 훅 유형(공통으로 통함): (없음)
- KO에서만 최종 엘리트에 든 훅 유형: (없음)
- EN에서만 최종 엘리트에 든 훅 유형: ['부정형', '역설·반전']

- KO 총 호출/비용: 17 / $6.4135
- EN 총 호출/비용: 17 / $5.3856

[실행 경위 — 이 비교는 두 번의 실행을 합친 것입니다]

한 프로세스에서 KO·EN 을 함께 돌리던 첫 시도는 EN 첫 호출에서 죽었습니다. 미국
페르소나 25명의 프롬프트가 35,903자로 한국어(13,304자)의 2.7배가 되어 Windows
명령줄 상한 32,767자를 넘겼기 때문입니다(FileNotFoundError WinError 206).
프롬프트를 인자 대신 표준입력으로 넘기도록 고친 뒤 EN 만 같은 결과 디렉토리에
이어 실행했습니다. 이미 완주한 KO 를 다시 돌리지 않아 $6.41 을 아꼈습니다.
두 트랙 모두 seed=42, 동일 코드, 동일 판정 스키마이므로 비교 가능합니다.
다만 KO 는 수정 전 코드로, EN 은 수정 후 코드로 돌았습니다. 수정 내용은 프롬프트
전달 경로(argv -> stdin)뿐이고 프롬프트 내용·모델·스키마는 동일합니다.
