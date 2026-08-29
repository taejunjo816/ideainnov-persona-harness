**한국어** | [English](README.en.md)

# IDEAINNOV.COM 합성 페르소나 하네스

**Threads에서 본 아이디어에 영감받아 직접 재구현하고, 실제 비용까지 전부 공개 검증한 프로젝트입니다.**

이 프로젝트가 내세우는 건 딱 세 가지입니다.

1. **원 아이디어 크레딧** — Dongkyu Lee(@dominic_kyu)님의 Threads 게시물에서 아이디어를 얻었습니다. 원본을 베낀 게 아니라 그 아이디어에서 출발했다는 걸 명확히 밝힙니다.
2. **독립 재구현** — 원 저장소 링크(`github.com/Dongk...`)는 이미지에서 잘려 있었고, 여러 차례 검색해도 원본 코드를 찾지도 열어보지도 못했습니다. 그래서 게시물 두 개에 서술된 메커니즘 설명만 근거로 **코드를 처음부터 새로 짰습니다** — 원본과 한 줄도 대조해본 적이 없습니다.
3. **실행 검증 + 비용 전부 공개** — "이론상 되겠다"에서 멈추지 않고, 실제 NVIDIA 데이터와 실제 `claude` CLI 호출로 **두 차례 실제로 돌렸고**, 호출 1건 단위 로그까지 남겨 총 실비용 **$0.4115**를 그대로 공개합니다. (참고: 검색으로 원본을 못 찾은 게 NVIDIA가 뭔가를 철회했다는 뜻은 아닙니다 — NVIDIA의 Nemotron-Personas 데이터셋 자체는 지금도 공개·CC BY 4.0 상태이며, 단순히 원 게시물이 올라온 지 하루이틀밖에 안 돼 검색엔진에 아직 색인되지 않았을 가능성이 훨씬 높습니다.)

원 게시물이 설명한 아이디어는 이렇습니다:

> 제품 아이디어가 생기면 설문 대신 가상 인구한테 물어본다. NVIDIA가 공개한 10개국 합성
> 페르소나(한국인 100만 명 포함)에 제품을 대입해서, 누가 쓰고/왜 안 쓰고/누가 돈을 내는지를
> AI 에이전트가 국가별로 분석한다. 웹앱도 서버도 없이 Claude Code + 데이터로 끝. 페르소나
> 1명당 LLM을 1번씩 부르면 파산하니 1호출이 25명을 한꺼번에 판정(100명 시뮬 = 4호출)하고,
> 노드끼리 대화시키는 대신 1차 판정을 집계해 "여론 요약"으로 2차 판정에 반영한다.

## 데이터 출처 (Attribution)

`data/`의 실제 페르소나 데이터는 **NVIDIA의 [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) 데이터셋 (CC BY 4.0)** 에서 가져온 것입니다.
이 저장소를 공개/재배포할 때는 이 출처 표시를 유지해야 합니다 — 세부 조건과 정확히 어떤 행이
실제 데이터셋 행이고 어떤 행이 (그렇지 않은) 직접 구성한 예시 페르소나인지는
[`data/ATTRIBUTION.md`](data/ATTRIBUTION.md)에 정리해뒀습니다.

## 무엇을 검증했는가

| | |
|---|---|
| 대상 제품 | [IDEAINNOV.COM](https://ideainnov.com) — 연구 아이디어→PDE 지배방정식 도출/검증→논문 초안 자동화 플랫폼 (WebFetch로 직접 조사, `product/ideainnov.json`) |
| 페르소나 데이터 | 실제 `nvidia/Nemotron-Personas-Korea` 데이터셋(100만 행, 한국 인구 통계에 정렬된 합성 페르소나) 중 25행을 Hugging Face datasets-server API로 직접 조회 |
| 실행 엔진 | 로컬 환경에 설치된 `claude` CLI (Claude Code 2.1.251)를 서브프로세스로 호출 — 서버도 API 키도 필요 없음 |
| 실제 실행 | 1차 판정(25명, 1콜) → 집계 → 2차 판정(25명, 1콜) 전체 파이프라인을 실제로 완주, 실비용 **$0.2183** |

## 파일 구조

```
ideainnov-harness/
├── data/
│   ├── personas_kr_batch1.jsonl        # 실제 데이터셋에서 가져온 일반 인구 페르소나 25명 (검증용 시드 배치)
│   ├── personas_kr_core_segment.jsonl  # 코어 세그먼트 17명 (real_dataset 12 + illustrative_construction 5)
│   ├── _seed_batch1_kr.py              # batch1의 출처/재현 스크립트 (정확히 어떤 offset에서 가져왔는지)
│   ├── _seed_batch2_core_segment.py    # 코어 세그먼트 구성 스크립트 (어느 행이 실제/구성인지 명시)
│   ├── prepare_personas.py             # 실전용: 인터넷 되는 환경에서 10개국 데이터셋 전체 스트리밍 샘플링
│   └── ATTRIBUTION.md                  # 데이터 출처(NVIDIA, CC BY 4.0) 및 실제/구성 행 구분
├── product/
│   └── ideainnov.json                  # IDEAINNOV.COM 제품 스펙 (WebFetch 조사 결과)
├── harness/
│   ├── schemas.py                      # 1차/2차 판정 JSON Schema (claude --json-schema로 강제)
│   └── run_harness.py                  # 메인 실행 스크립트
├── results/
│   ├── dry_run/                        # 무료 스텁으로 파이프라인 전체를 즉시 검증한 결과
│   ├── kr_real_run/                    # 일반 인구 25명 실제 claude 호출 결과 (final_report.md 필독)
│   └── kr_core_segment_run/            # 코어 세그먼트 17명 실제 호출 결과
└── README.md
```

## 메커니즘 (원 게시물 → 구현 매핑)

1. **"1호출이 25명을 한꺼번에 판정"** — `run_harness.py`가 페르소나를 25개씩 묶어(batch),
   배치당 `claude -p` 1회만 호출합니다. `--json-schema`로 정확히 그 배치 크기만큼의 판정을
   같은 순서로 강제 반환시켜서 파싱이 깨지지 않게 했습니다. 시스템 프롬프트 규칙 1번으로
   "같은 배치 내 페르소나끼리 서로 영향받지 말 것"을 명시해 교차 오염을 최소화했습니다
   (이것이 배치 방식의 근본적 한계이기도 합니다 — 아래 "알려진 한계" 참고).
2. **"노드끼리 대화 대신 여론 요약"** — 1차 판정 결과는 LLM을 다시 부르지 않고 순수
   집계(퍼센트, Counter, 중앙값)로 "공론 요약" 문단을 만듭니다(`aggregate()` +
   `render_opinion_summary_text()`). 이 요약 텍스트만 2차 판정 프롬프트에 넣어 각
   페르소나가 "전체 여론을 알게 된 뒤" 재판단하게 합니다 — 페르소나 수가 늘어도 비용이
   O(N²)가 아니라 O(N)으로 유지됩니다.
3. **"웹앱도 서버도 없이 Claude Code + 데이터"** — Flask/FastAPI 등 서버 없음. Python
   스크립트가 로컬 JSONL/JSON 파일을 읽고 `claude` CLI를 서브프로세스로 부르는 것이 전부입니다.

## 실제 실행 결과 요약 (results/kr_real_run/final_report.md)

25명(일반 한국 성인 무작위 표본) 기준:

- **사용 의향 0%, "adjacent"(관련은 있으나 핵심 타깃 아님) 4%, 나머지 96% not_applicable**
- 유일하게 "adjacent"였던 페르소나는 53세 IT분야 대학원졸 연구원(엔지니어) — 그런데도
  "core_target"이 아니라 "adjacent"로 정확히 구분했습니다. 이유: 그의 실무는 IT 하드웨어
  신뢰성 검증이라 IDEAINNOV가 다루는 유체/재료/에너지/열/우주/경제 PDE 도메인과 결이
  다르다는, 학력만 보고 뭉뚱그리지 않은 구체적 판단이었습니다.
- 대학원졸 치과의사(의료보건)도 학력은 높지만 "임상 진료 중심이라 PDE 논문 자동화와 무관"으로
  정확히 no 처리됨.
- 2차 판정에서 바뀐 사람: **0/25 (0%)** — 이미 "내 일과 무관하다"고 판단한 사람들은 "다들
  안 쓴다더라"는 정보를 들어도 입장을 바꿀 이유가 없다는, 상식적으로 타당한 결과입니다.

**해석상 중요한 포인트**: 이 결과는 하네스가 "만들어도 소용없다"는 뜻이 아니라, *일반
인구 무작위 표본*은애초에 이런 니치 B2B 연구 도구를 검증하기에 적합한 표본이 아니라는
뜻입니다. Nemotron-Personas-Korea 전체 100만 명 중 "공학/재료/에너지 분야 대학원급
연구자"의 실제 비율은 아마 1% 미만일 것이므로, 무작위 25명 중 0명의 core_target이 나온 건
오히려 하네스가 올바르게 작동한다는 신호입니다. **후속 조치로 추천**: `prepare_personas.py`로
더 큰 표본(예: 2,000명)을 뽑거나, 직업/전공 필드로 사전 필터링한 표본으로 다시 돌리면
"핵심 타깃 내에서의" 사용/결제 의향을 훨씬 선명하게 볼 수 있습니다.

## 실행 방법

```bash
# 사전 준비: Claude Code CLI가 설치·로그인되어 있어야 함 (claude --version으로 확인)

# 1) 무료 드라이런 (파이프라인 로직만 검증, 비용 $0)
python3 harness/run_harness.py \
  --personas data/personas_kr_batch1.jsonl \
  --product  product/ideainnov.json \
  --out-dir  results/dry_run \
  --dry-run

# 2) 실제 실행 (배치 25명 x 2라운드 = 실제 claude 호출 2회, 실측 약 $0.22)
python3 harness/run_harness.py \
  --personas data/personas_kr_batch1.jsonl \
  --product  product/ideainnov.json \
  --out-dir  results/my_run

# 3) (다른 인터넷이 되는 머신에서) 더 큰/다른 나라 표본 만들기
pip install datasets huggingface_hub pandas pyarrow
python3 data/prepare_personas.py --country Korea --n 2000 --slim \
  --out data/personas_kr_2000.jsonl
python3 harness/run_harness.py \
  --personas data/personas_kr_2000.jsonl --product product/ideainnov.json \
  --out-dir results/kr_2000 --batch-size 25
# 100명 표본이면 4콜/라운드, 2,000명이면 80콜/라운드 — 위 실측 단가($0.109/25명/라운드)로
# 어림하면 2,000명 x 2라운드 ≈ $17 안팎으로 예상됩니다.
```

주요 플래그: `--batch-size`(기본 25), `--model`(claude CLI별칭, 기본은 계정 기본모델),
`--max-budget-usd`(콜당 상한, 기본 2.0), `--country`(리포트 라벨용).

## 후속 실행: 코어 타깃 세그먼트 (연구원/대학원생/공학·재료·에너지 전공)

`results/kr_core_segment_run/` — `data/personas_kr_core_segment.jsonl`(17명)로 재실행한 결과.
두 종류를 한 배치에 섞되 `source` 필드로 구분:

- `real_dataset` 12명: 실제 데이터셋에서 "직업/전공이 엔지니어링·기술직에 가까운" 사람만 스캔해서 찾은 진짜 행. 필터/서치 API가 이 데이터셋에서 지원되지 않아(422/500 에러) `/rows`로 여러 offset을 훑어 클라이언트 사이드로 골라냈습니다.
- `illustrative_construction` 5명: IDEAINNOV가 명시한 도메인(유체·재료·에너지·항공우주·경제)에 정확히 맞춰 직접 구성한 "이상적 유저" 페르소나. 데이터셋 행이 아님 — README 등 어디서든 이 점을 반드시 밝혀야 함(`data/ATTRIBUTION.md` 참고).

**결과**: real_dataset 12명은 전원(12/12) not_applicable, illustrative_construction 5명은 전원(5/5) core_target + would_pay=yes. 즉 "직업이 엔지니어"인 것만으로는 부족하고, "실제로 학위논문/SCI 논문을 써야 하는 사람"이어야 core_target으로 잡힙니다. 이 5명의 reasoning/objection(예산, 보안, 인용 신뢰성 등)이 실제로 쓸모 있는 부분입니다:

| 페르소나(구성) | 판정 | 진짜 반대 이유 | 월 지불 의향 |
|---|---|---|---|
| 재료공학 박사과정 | core_target / pay=yes | "필요하지만 지도교수 연구비 지원 없이는 구독 지속이 부담" | ₩25,000~30,000 |
| 배터리 기업 선임연구원·항공우주연구원 | core_target / pay=yes | "연구 데이터를 외부 AI 서버에 올리는 것에 대한 보안·특허 유출 우려" | ₩50,000~130,000 |
| 유체역학 부교수 | core_target / pay=yes | "AI가 쓴 초안의 학술적 신뢰성·인용 정확성을 누가 검증하나" | ₩120,000 |

가격이 아니라 **예산 승인·보안 승인·검증 책임**이 진짜 장벽이라는 뜻입니다(단, 위 5명은 구성 페르소나이므로 실제 고객 인터뷰의 대체물이 아닙니다). 지불 의향자 5명의 월 최대 지불액 중앙값은 1차 판정 ₩50,000(평균 ₩71,000)에서 여론 요약을 인지한 2차 판정 ₩45,000(평균 ₩52,000)으로 낮아졌습니다.

이번 코어 세그먼트 실행의 실비용은 **$0.1932**이며, 두 번의 실제 실행(일반 인구 $0.2183 +
코어 세그먼트 $0.1932) 합계 실비용은 **$0.4115**입니다.

## 알려진 한계 / 다음에 개선할 점

- **배치 내 교차 오염 가능성**: 25명을 한 컨텍스트에 몰아넣으면, 명시적으로 금지했음에도
  모델이 앞선 페르소나의 판단에 은근히 영향받을 이론적 위험이 있습니다. 완전히 배제하려면
  배치 순서를 섞어 여러 번 돌리고 분산을 확인하는 방법이 있으나, 그만큼 비용이 늘어납니다.
- **표본 편향**: 이번 검증에 쓴 25명은 offset 0-25 구간이라 고령층 비중이 다소 높았습니다
  (완전 무작위 셔플은 아님). `prepare_personas.py`의 저수지 표본(reservoir sampling)을
  실제 인터넷이 되는 환경에서 돌리면 이 편향이 해소됩니다.
- **데이터 수집 환경의 제약**: 네트워크가 제한된 환경에서는 huggingface.co/pypi.org로의 직접
  `curl`/`pip install`이 막혀 있어, `datasets` 라이브러리로 원본 parquet을 직접 읽는 대신
  Hugging Face의 datasets-server REST API를 웹 프록시로 우회 조회했습니다. 15개 행은
  한국어 원문 그대로, 10개 행은 프록시가 영어로 의역해 반환했습니다 — 실제 서비스에서는
  `prepare_personas.py`로 parquet을 직접 읽어 이런 손실을 없애야 합니다.
- **10개국 확장**: `prepare_personas.py`는 이미 10개국 데이터셋 ID를 전부 매핑해뒀지만
  (`COUNTRY_TO_DATASET`), 이번 실제 검증 실행은 비용/시간상 한국 표본 1건만 진행했습니다.
  `--country` 값만 바꿔 다른 나라로 그대로 확장 가능합니다.
- **원 저장소 미확인**: 위에서 설명한 대로 원문에서 잘린 GitHub 링크를 찾지 못했습니다.
  원 저장소를 확인하게 되면 diff를 반영해 이 재구현을 더 가깝게 맞출 예정입니다.

## 라이선스 (License)

- **코드**: 별도 라이선스 파일이 아직 없습니다 — 소유자가 라이선스를 정하기 전까지는 모든
  권리를 보유(all rights reserved)합니다. 평가 목적의 fork·실행은 환영합니다.
- **데이터**: `data/` 하위 데이터는 CC BY 4.0이며, 조건은
  [`data/ATTRIBUTION.md`](data/ATTRIBUTION.md)를 따릅니다.
