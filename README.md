한국어 | [English](README.en.md)

IDEAINNOV.COM 합성 페르소나 하네스

- 원 아이디어 크레딧 — Dongkyu Lee(@dominic_kyu)님의 Threads 게시물.
- 독립 재구현 — 원 저장소 링크가 잘려 원본 코드를 찾지도 열어보지도 못했고, 게시물 설명만 보고 새로 짰습니다. 원본과 한 줄도 대조한 적 없습니다.
- 실행 검증 — 실제 데이터와 `claude` CLI로 2회 실행(각 2콜 = claude 호출 4건), 총 실비용 $0.4115(일반 $0.2183 + 코어 $0.1932).
- 대상 제품 — [IDEAINNOV.COM](https://ideainnov.com): 유체·재료·에너지·열·우주·경제 도메인의 연구 아이디어에서 PDE 도출·검증을 거쳐 논문 초안까지 자동화. 설문 대신 합성 인구에게 누가 쓰고 왜 안 쓰고 누가 돈을 내는지 묻습니다.

[데이터 출처]

NVIDIA [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) 100만 행, CC BY 4.0. 실제 행과 직접 구성한 행의 구분은 `data/ATTRIBUTION.md`(영문 `.en.md`)에 있습니다.

[메커니즘 — 원 게시물에서 구현으로]

| 원 게시물 | 구현 |
|---|---|
| 1호출이 25명 판정 | `claude -p` 1회로 배치 25건, `--json-schema`로 순서 강제 |
| 노드 대화 대신 여론 요약 | 1차 판정을 재호출 없이 집계해 2차 프롬프트에 투입, 비용이 O(N²)가 아니라 O(N) |
| 서버 없이 Claude Code | 로컬 JSONL을 읽고 `claude` CLI를 서브프로세스로 호출 |

[실제 실행 결과 — 로그는 `results/`]

| 표본 | 결과 |
|---|---|
| 일반 25명 | 사용 의향 0%, adjacent 4%, not_applicable 96%, 2차 판정 변화 0/25 |
| 코어 세그먼트 17명 중 `real_dataset` 12명 | 12/12 not_applicable |
| 코어 `illustrative_construction` 5명 | 5/5 core_target + would_pay=yes |

고지: `illustrative_construction` 5명은 데이터셋 행이 아니라 직접 구성한 페르소나이며, 실제 고객 인터뷰의 대체물이 아닙니다.

0%는 오작동이 아닙니다. 100만 행 중 대학원급 공학·재료·에너지 연구자는 1%에 훨씬 못 미쳐 무작위 25명에 0명이 정상입니다. 판별은 학력이 아니라 도메인 기준입니다. 유일한 adjacent였던 대학원졸 IT 연구원도 주업무가 하드웨어 신뢰성 검증이라 PDE와 결이 다르다고 스스로 선을 그었고, 엔지니어 직업만으론 부족해 학위논문이나 SCI 논문을 쓰는 사람이라야 core_target이었습니다. 장벽은 가격이 아니라 지도교수 연구비 의존(월 2.5~3만원), 연구데이터 외부 업로드의 특허·보안 우려(월 5~13만원), AI 초안 인용 검증 책임(월 12만원)입니다. 여론 요약을 본 2차에서 지불 의향 중앙값은 ₩50,000에서 ₩45,000으로, 평균은 ₩71,000에서 ₩52,000으로 내려갔습니다.

[실행 방법]

```bash
# 사전: claude --version
H="python3 harness/run_harness.py --product product/ideainnov.json --personas data/personas_kr_batch1.jsonl"

# 1) 드라이런 $0
$H --out-dir results/dry_run --dry-run

# 2) 실제 실행 2콜, 실측 $0.22 (--max-budget-usd 로 상한)
$H --out-dir results/my_run

# 3) 대량 표본 (인터넷 필요)
pip install datasets huggingface_hub pandas pyarrow
python3 data/prepare_personas.py --country Korea --n 2000 --slim --out data/personas_kr_2000.jsonl
# 2,000명 x 2라운드 ≈ $17 (단가 $0.109/25명/라운드)
```

[알려진 한계]

- 교차 오염: 프롬프트로 금지했으나 25명이 한 컨텍스트를 공유해 앞선 판단에 영향받을 위험. 배제하려면 순서를 섞어 재실행해야 합니다.
- 수집 제약: parquet 직독 대신 datasets-server API를 우회 조회했습니다. 15행은 한국어 원문, 10행은 영어 의역본입니다.
- 표본 편향: offset 0-25 구간이라 고령층 비중이 높습니다. `prepare_personas.py`의 저수지 표본으로 해소할 수 있습니다.

[확장 — 같은 하네스로 광고 문구 진화시키기 (copy-optimizer/)]

`product/ideainnov.json` 자리에 광고 문구를 넣고 판정 스키마를 "이 문구를 보고 클릭하겠는가, 무엇이 걸리는가"로 바꾸면, 같은 메커니즘이 문구 최적화기가 됩니다. 그 구현이 `copy-optimizer/` 입니다.

동작: 사람이 쓴 시드 문구 8개를 25명에게 판정시켜 점수를 매기고, 상위 3개를 남겨 하위권의 걸림돌을 재료로 자식 5개를 만들어 다음 세대로 넘깁니다. 점수는 `100*P(yes) + 40*P(maybe) + 8*평균신뢰도` 입니다.

실행 결과(2026-09-01~02, 5세대, 실비용 26.45달러 / 76콜):

| 세대 | 한국어 최고 | 영어 최고 |
|---:|---:|---:|
| 0 | 37.76 | 37.12 |
| 1 | 55.68 | 35.20 |
| 2 | 49.44 | 38.88 |
| 3 | 68.00 | 40.32 |
| 4 | 72.16 | 43.84 |

우승 문구는 `copy-optimizer/copy/winning_ko.json` 과 `winning_en.json`, 전체 리포트는 `copy-optimizer/results/` 에 있습니다.

읽을 때 주의할 점 세 가지가 있습니다.

첫째, 이 점수는 합성 페르소나가 예측한 시뮬레이션 클릭 의향이며 실제 클릭률이 아닙니다. 실측 A/B 테스트의 대체물이 아닙니다.

둘째, 영어는 점수가 올랐지만 평균 신뢰도는 3.44에서 2.48로 떨어졌습니다. 점수 함수가 클릭 의향에 100과 40, 신뢰도에는 8만 주기 때문에 신뢰를 잃어도 관심만 끌면 점수가 오릅니다. 가중치를 바꾸면 다른 문구가 이깁니다.

셋째, 두 언어가 서로 다른 제품으로 갈라졌습니다. 한국어는 문서 변환, 영어는 사업제안서로 수렴했고, 미국 표본은 한글 파일 문제를 자기 일과 무관하다고 판단했습니다. 한글 형식 문제가 한국 고유의 것이라는 해석과 일치합니다.

표본은 무작위가 아니라 필터를 거쳤습니다. 조건과 통과율은 `data/ATTRIBUTION.md` 에 있습니다.

실행 방법:

```bash
cd copy-optimizer
# 무료 드라이런 — 유료 호출 없이 전 구간을 밟아 본다
python3 optimize/evolve.py --lang both --generations 2 --dry-run   --personas-ko data/personas_kr_25_filtered.jsonl   --personas-en data/personas_us_25_filtered.jsonl --out-dir results/dry

# 실제 실행. 첫 유료 호출 전에 비용 상한을 투사하고, 넘으면 시작하지 않는다
python3 optimize/evolve.py --lang both --generations 2 --max-budget-usd 15   --personas-ko data/personas_kr_25_filtered.jsonl   --personas-en data/personas_us_25_filtered.jsonl --out-dir results/my_run

# 이전 실행의 엘리트에서 이어 돌리기 (시드부터 다시 시작하지 않는다)
python3 optimize/evolve.py --lang both --generations 3 --resume-from results/my_run   --out-dir results/my_run_more
```

[영상 (video/)]

`video/` 에 22초 세로 릴스 3편이 있습니다. 1080x1920, 30fps 입니다.

- `릴스_persona_harness_KO_22s_2026-08-31.mp4` — 이 하네스 자체(사전 수요 검증)를 소개
- `릴스_ideainnov_카피최적화_KO_22s_2026-09-02_gen4.mp4` — 세대 4 한국어 우승 문구
- `릴스_ideainnov_카피최적화_EN_22s_2026-09-02_gen4.mp4` — 세대 4 영어 우승 문구

빌더는 `copy-optimizer/video/build_copy_reel_22s.py` 입니다. 영상 안의 모든 수치는 제품 사실표에서 가져오며, 근거를 댈 수 없는 주장은 빌더가 거부합니다.

[라이선스]

- 코드: 라이선스 미정, 모든 권리 보유.
- 데이터: CC BY 4.0, 조건은 `data/ATTRIBUTION.md`를 따릅니다.
