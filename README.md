**한국어** | [English](README.en.md)

# IDEAINNOV.COM 합성 페르소나 하네스

- **원 아이디어 크레딧** — Dongkyu Lee(@dominic_kyu)님의 Threads 게시물.
- **독립 재구현** — 원 저장소 링크가 잘려 원본 코드를 찾지도 열어보지도 못했고, 게시물 설명만 보고 새로 짰습니다. 원본과 한 줄도 대조한 적 없습니다.
- **실행 검증** — 실제 데이터·`claude` CLI로 2회 실행(각 2콜 = claude 호출 4건), 총 실비용 **$0.4115**(일반 $0.2183 + 코어 $0.1932).
- **대상 제품** — [IDEAINNOV.COM](https://ideainnov.com): 유체·재료·에너지·열·우주·경제 도메인의 연구 아이디어→PDE 도출·검증→논문 초안 자동화. 설문 대신 합성 인구에게 누가 쓰고 왜 안 쓰고 누가 돈을 내는지 묻습니다.

## 데이터 출처

NVIDIA [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) 100만 행, **CC BY 4.0**. 실제/구성 행 구분: `data/ATTRIBUTION.md`(`.en.md`).

## 메커니즘 (원 게시물 → 구현)

| 원 게시물 | 구현 |
|---|---|
| 1호출이 25명 판정 | `claude -p` 1회로 배치 25건, `--json-schema`로 순서 강제 |
| 노드 대화 대신 여론 요약 | 1차 판정을 재호출 없이 집계해 2차 프롬프트에 투입(O(N²)→O(N)) |
| 서버 없이 Claude Code | 로컬 JSONL을 읽고 `claude` CLI를 서브프로세스 호출 |

## 실제 실행 결과 (로그 `results/`)

| 표본 | 결과 |
|---|---|
| 일반 25명 | 사용 의향 **0%**, adjacent 4%, not_applicable 96%, 2차 변화 **0/25** |
| 코어 세그먼트 17명 중 `real_dataset` 12명 | 2차 기준 **12/12 not_applicable** |
| 코어 `illustrative_construction` 5명 | **5/5 core_target + would_pay=yes** |

> ★ `illustrative_construction` 5명은 데이터셋 행이 아니라 **직접 구성한 페르소나**이며, 실제 고객 인터뷰의 대체물이 아닙니다.

0%는 오작동이 아닙니다. 100만 행 중 대학원급 공학·재료·에너지 연구자는 1%에 훨씬 못 미쳐 무작위 25명에 0명이 정상입니다. 판별은 학력이 아니라 도메인 기준입니다 — 유일한 adjacent(대학원졸 IT 연구원)도 주업무가 하드웨어 신뢰성 검증이라 PDE와 결이 다르다고 스스로 선을 그었고, 엔지니어 직업만으론 부족해 학위논문·SCI를 쓰는 사람이라야 core_target이었습니다. 장벽은 가격이 아니라 지도교수 연구비 의존(월 2.5~3만원), 연구데이터 외부 업로드의 특허·보안 우려(월 5~13만원), AI 초안 인용 검증 책임(월 12만원)입니다. 2차에서 중앙값 ₩50,000→₩45,000, 평균 ₩71,000→₩52,000.

## 실행 방법

```bash
# 사전: claude --version
H="python3 harness/run_harness.py --product product/ideainnov.json --personas data/personas_kr_batch1.jsonl"

# 1) 드라이런 $0
$H --out-dir results/dry_run --dry-run

# 2) 실제 실행 2콜, 실측 $0.22 (--max-budget-usd 상한)
$H --out-dir results/my_run

# 3) 대량 표본 (인터넷 필요)
pip install datasets huggingface_hub pandas pyarrow
python3 data/prepare_personas.py --country Korea --n 2000 --slim --out data/personas_kr_2000.jsonl
# 2,000명 x 2라운드 ≈ $17(단가 $0.109/25명/라운드)
```

## 알려진 한계

- **교차 오염**: 프롬프트로 금지했으나 25명이 한 컨텍스트를 공유해 앞선 판단에 영향받을 위험. 배제하려면 순서를 섞어 재실행.
- **수집 제약**: parquet 직독 대신 datasets-server API 우회 — 15행은 한국어 원문, **10행은 영어 의역본**.
- **표본 편향**: offset 0-25 구간이라 고령층 비중이 높음. `prepare_personas.py` 저수지 표본으로 해소.

## 라이선스

- **코드**: 라이선스 미정, 모든 권리 보유. **데이터**: CC BY 4.0(`data/ATTRIBUTION.md`).