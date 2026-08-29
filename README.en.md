[한국어](README.md) | **English**

# IDEAINNOV.COM Synthetic Persona Harness

**Inspired by an idea seen on Threads, independently re-implemented from scratch, with real cost fully disclosed.**

This project makes exactly three claims.

1. **Credit for the original idea** — The idea came from a Threads post by Dongkyu Lee (@dominic_kyu). This is explicitly *not* a copy of the original — it is a re-implementation starting from that idea.
2. **Independent re-implementation** — The original repo link (`github.com/Dongk...`) was cut off in the post's image, and repeated searches never located or opened the original code. So the code here was **written from scratch**, based only on the mechanism described in two posts — it has never been diffed against the original, line by line.
3. **Execution verified + full cost disclosure** — Rather than stopping at "this should work in theory," the harness was **actually run twice** against real NVIDIA data with real `claude` CLI calls, with per-call logs kept, for a total real cost of **$0.4115**, disclosed as-is. (Note: not finding the original repo via search does not mean NVIDIA withdrew anything — the NVIDIA Nemotron-Personas dataset itself is still public and CC BY 4.0; it's far more likely that the original post is only a day or two old and simply hasn't been indexed by search engines yet.)

The idea described in the original post, in short:

> When you have a product idea, instead of running a survey, ask a synthetic population.
> Take NVIDIA's publicly released synthetic personas for 10 countries (including 1 million
> Koreans), feed the product to them, and have AI agents analyze — per country — who would
> use it, who wouldn't and why, and who would pay. No web app, no server — just Claude Code
> plus data. Since calling the LLM once per persona would be prohibitively expensive, one call
> judges 25 personas at once (a 100-person simulation = 4 calls), and instead of having the
> personas "talk" to each other node-to-node, the first-round verdicts are aggregated into an
> "opinion summary" that feeds into a second round of judging.

## Data Source (Attribution)

The actual persona data under `data/` comes from **NVIDIA's [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) dataset (CC BY 4.0)**.
This attribution must be preserved whenever this repository is published or redistributed —
the detailed terms, and exactly which rows are real dataset rows versus directly constructed
illustrative personas, are laid out in [`data/ATTRIBUTION.md`](data/ATTRIBUTION.md)
(English version: [`data/ATTRIBUTION.en.md`](data/ATTRIBUTION.en.md)).

## What Was Verified

| | |
|---|---|
| Target product | [IDEAINNOV.COM](https://ideainnov.com) — a platform that automates research idea → PDE governing-equation derivation/verification → paper draft (researched directly via WebFetch, `product/ideainnov.json`) |
| Persona data | 25 rows queried directly via the Hugging Face datasets-server API from the actual `nvidia/Nemotron-Personas-Korea` dataset (1M rows, synthetic personas aligned to Korean population statistics) |
| Execution engine | The `claude` CLI (Claude Code 2.1.251) installed in the local environment, invoked as a subprocess — no server, no API key needed |
| Actual run | Full pipeline — round-1 judging (25 people, 1 call) → aggregation → round-2 judging (25 people, 1 call) — completed end to end for real, at a real cost of **$0.2183** |

## Results at a Glance (EN)

| Run | Sample | Core-target rate | Round-2 flip rate | Real cost |
|---|---|---|---|---|
| General population (`kr_real_run`) | 25 random Korean adults | 0% core_target, 4% adjacent, 96% not_applicable | 0/25 (0%) | $0.2183 |
| Core target segment (`kr_core_segment_run`) | 12 real_dataset + 5 illustrative_construction | real_dataset 0/12 (0%); illustrative_construction 5/5 (100%), all would_pay=yes | — | $0.1932 |
| **Total (both real runs)** | | | | **$0.4115** |

## File Structure

```
ideainnov-harness/
├── data/
│   ├── personas_kr_batch1.jsonl        # 25 general-population personas pulled from the real dataset (seed batch for verification)
│   ├── personas_kr_core_segment.jsonl  # Core segment of 17 (real_dataset 12 + illustrative_construction 5)
│   ├── _seed_batch1_kr.py              # Provenance/reproduction script for batch1 (exactly which offset each row came from)
│   ├── _seed_batch2_core_segment.py    # Core-segment construction script (states which rows are real vs. constructed)
│   ├── prepare_personas.py             # Production use: full streaming sample of the 10-country dataset from a machine with internet access
│   └── ATTRIBUTION.md / ATTRIBUTION.en.md  # Data source (NVIDIA, CC BY 4.0) and real-vs-constructed row breakdown
├── product/
│   └── ideainnov.json                  # IDEAINNOV.COM product spec (WebFetch research result)
├── harness/
│   ├── schemas.py                      # JSON Schema for round-1/round-2 verdicts (enforced via claude --json-schema)
│   └── run_harness.py                  # Main execution script
├── results/
│   ├── dry_run/                        # Result of instantly validating the whole pipeline with a free stub
│   ├── kr_real_run/                    # Result of the real claude calls against 25 general-population personas (see final_report.md)
│   └── kr_core_segment_run/            # Result of the real calls against the 17-person core segment
└── README.md / README.en.md
```

## Mechanism (Original Post → Implementation Mapping)

1. **"One call judges 25 people at once"** — `run_harness.py` batches personas into groups of
   25 and makes exactly one `claude -p` call per batch. `--json-schema` forces the same-order
   return of exactly that many verdicts, so parsing never breaks. System-prompt rule #1
   explicitly states "personas within the same batch must not influence each other," minimizing
   cross-contamination (this is also a fundamental limitation of the batching approach — see
   "Known Limitations" below).
2. **"Opinion summary instead of node-to-node dialogue"** — Round-1 verdicts are not fed back
   into another LLM call; instead they're pure-aggregated (percentages, `Counter`, median) into
   an "opinion summary" paragraph (`aggregate()` + `render_opinion_summary_text()`). Only this
   summary text is inserted into the round-2 prompt, so each persona re-judges "after learning
   what the public thinks" — keeping cost at O(N) rather than O(N²) as the persona count grows.
3. **"No web app, no server — just Claude Code + data"** — No Flask/FastAPI or any server. It's
   entirely a Python script reading local JSONL/JSON files and invoking the `claude` CLI as a
   subprocess.

## Summary of the Real Run Results (results/kr_real_run/final_report.md)

Based on 25 people (a random sample of general Korean adults):

- **Willingness to use: 0%; "adjacent" (related but not core target): 4%; the remaining 96%: not_applicable**
- The one "adjacent" persona was a 53-year-old IT-field researcher/engineer with a graduate
  degree — and even so, the model correctly classified them as "adjacent," not "core_target."
  Reason: their actual work is IT hardware reliability testing, which doesn't align with
  IDEAINNOV's fluid/materials/energy/thermal/aerospace/economics PDE domains — a specific
  judgment, not a blanket "graduate degree = target" assumption.
- A dentist (healthcare) with a graduate degree was likewise correctly marked "no," reasoned as
  "clinical practice-focused, unrelated to PDE paper automation."
- People who changed their verdict in round 2: **0/25 (0%)** — people who had already judged
  "this is irrelevant to my work" had no reason to change their stance after hearing "most
  people don't use this either." A sensible, expected result.

**An important interpretive point**: this result does not mean the harness shows "this product
is useless" — it means a *random sample of the general population* was never the right sample
to validate this kind of niche B2B research tool in the first place. Out of the full 1 million
Nemotron-Personas-Korea rows, the real share of "graduate-level researchers in
engineering/materials/energy" is probably well under 1%, so getting 0 core_targets out of a
random 25 is arguably a signal the harness is working correctly. **Recommended next step**:
pull a larger sample (e.g., 2,000) with `prepare_personas.py`, or pre-filter by
occupation/major field, to get a much sharper read on usage/payment intent "within the core
target."

## How to Run

```bash
# Prerequisite: the Claude Code CLI must be installed and logged in (verify with claude --version)

# 1) Free dry run (validates pipeline logic only, cost $0)
python3 harness/run_harness.py \
  --personas data/personas_kr_batch1.jsonl \
  --product  product/ideainnov.json \
  --out-dir  results/dry_run \
  --dry-run

# 2) Real run (25-person batch x 2 rounds = 2 real claude calls, measured at about $0.22)
python3 harness/run_harness.py \
  --personas data/personas_kr_batch1.jsonl \
  --product  product/ideainnov.json \
  --out-dir  results/my_run

# 3) (On another machine with internet access) build a larger/other-country sample
pip install datasets huggingface_hub pandas pyarrow
python3 data/prepare_personas.py --country Korea --n 2000 --slim \
  --out data/personas_kr_2000.jsonl
python3 harness/run_harness.py \
  --personas data/personas_kr_2000.jsonl --product product/ideainnov.json \
  --out-dir results/kr_2000 --batch-size 25
# A 100-person sample is 4 calls/round; 2,000 people is 80 calls/round — extrapolating from
# the measured unit rate above ($0.109/25 people/round), 2,000 people x 2 rounds is expected
# to cost roughly $17.
```

Main flags: `--batch-size` (default 25), `--model` (a claude CLI alias; defaults to the
account's default model), `--max-budget-usd` (per-call cap, default 2.0), `--country` (report
label only).

## Follow-up Run: Core Target Segment (Researchers/Grad Students/Engineering·Materials·Energy Majors)

`results/kr_core_segment_run/` — the result of re-running against
`data/personas_kr_core_segment.jsonl` (17 people). Two kinds of rows mixed into one batch,
distinguished by the `source` field:

- `real_dataset` (12 people): real rows found by scanning the actual dataset for people whose
  "occupation/major is close to engineering/technical." Since filter/search APIs aren't
  supported on this dataset (422/500 errors), rows were picked client-side by paging through
  `/rows` at multiple offsets.
- `illustrative_construction` (5 people): "ideal user" personas directly constructed to match
  IDEAINNOV's stated domains (fluid dynamics, materials, energy, aerospace, economics). These
  are *not* dataset rows — this must always be disclosed, anywhere this data is referenced
  (see `data/ATTRIBUTION.md`).

**Result**: all 12 `real_dataset` personas (12/12) came back `not_applicable`; all 5
`illustrative_construction` personas (5/5) came back `core_target` + `would_pay=yes`. In other
words, "occupation = engineer" alone isn't enough — a persona has to be someone who "actually
needs to write a thesis or SCI paper" to land as `core_target`. The reasoning/objections from
these 5 (budget, security, citation trust, etc.) are the genuinely useful part:

| Persona (constructed) | Verdict | Real objection | Willingness to pay (monthly) |
|---|---|---|---|
| Materials-science PhD student | core_target / pay=yes | "필요하지만 지도교수 연구비 지원 없이는 구독 지속이 부담" (needed, but continuing the subscription is a burden without my advisor's research funding) | ₩25,000–30,000 |
| Senior researcher at a battery company / aerospace researcher | core_target / pay=yes | "연구 데이터를 외부 AI 서버에 올리는 것에 대한 보안·특허 유출 우려" (concern about security/patent leakage from uploading research data to an external AI server) | ₩50,000–130,000 |
| Fluid-dynamics associate professor | core_target / pay=yes | "AI가 쓴 초안의 학술적 신뢰성·인용 정확성을 누가 검증하나" (who verifies the academic reliability and citation accuracy of an AI-written draft) | ₩120,000 |

This means the real barrier isn't price — it's **budget approval, security approval, and
verification responsibility** (note: these 5 are constructed personas, so they are not a
substitute for real customer interviews). Among the 5 willing to pay, the median maximum
monthly price dropped from ₩50,000 (mean ₩71,000) in round 1 to ₩45,000 (mean ₩52,000) in
round 2, after they'd seen the opinion summary.

The real cost of this core-segment run was **$0.1932**, and the total real cost across both
actual runs (general population $0.2183 + core segment $0.1932) is **$0.4115**.

## Known Limitations / Future Improvements

- **Possible cross-contamination within a batch**: cramming 25 people into one context carries
  a theoretical risk that the model is subtly influenced by an earlier persona's judgment, even
  though this is explicitly forbidden. Fully ruling this out would mean shuffling batch order
  and re-running multiple times to check variance, at proportionally higher cost.
- **Sample bias**: the 25 people used in this verification came from the offset 0–25 range, so
  the sample skewed somewhat older (not a fully random shuffle). Running
  `prepare_personas.py`'s reservoir sampling from an environment with real internet access
  would remove this bias.
- **Constraints of the data-collection environment**: in a network-restricted environment,
  direct `curl`/`pip install` access to huggingface.co/pypi.org is blocked, so instead of
  reading the original parquet directly via the `datasets` library, the Hugging Face
  datasets-server REST API was queried through a web proxy. Of the rows retrieved this way, 15
  came back as original Korean text, and 10 came back paraphrased into English by the proxy —
  a production deployment should read the parquet directly via `prepare_personas.py` to avoid
  this loss.
- **10-country expansion**: `prepare_personas.py` already maps all 10 country dataset IDs
  (`COUNTRY_TO_DATASET`), but this particular real-verification run only covered the Korean
  sample, for cost/time reasons. Changing just the `--country` value extends it to any other
  country as-is.
- **Original repository unconfirmed**: as noted above, the GitHub link cut off in the original
  post could not be found. If the original repository is confirmed, its diff will be
  incorporated to bring this re-implementation closer to the original.

## License

- **Code**: no license file yet — all rights reserved until the owner picks one. Forking and
  running it for evaluation purposes is welcome.
- **Data**: the data under `data/` is CC BY 4.0, under the terms in
  [`data/ATTRIBUTION.md`](data/ATTRIBUTION.md) / [`data/ATTRIBUTION.en.md`](data/ATTRIBUTION.en.md).
