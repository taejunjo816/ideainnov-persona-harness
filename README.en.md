[한국어](README.md) | English

IDEAINNOV.COM Synthetic Persona Harness

Idea credit: a Threads post by Dongkyu Lee (@dominic_kyu). Not a copy: the repo link was cut off in the post's image and searches never found or opened that code, so this was written from scratch off the described mechanism, never diffed against the original.

Instead of a survey, ask a synthetic population who would use it, who would not, and who would pay. Product: [IDEAINNOV.COM](https://ideainnov.com) — automating research idea, PDE governing-equation derivation and verification, and paper drafting across fluid dynamics, materials, energy, thermal, aerospace and economics.

Data: `data/` rows are NVIDIA [Nemotron-Personas-Korea](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) (1M rows), CC BY 4.0; attribution required. [`ATTRIBUTION.md`](data/ATTRIBUTION.md) marks real vs. constructed rows.

[Mechanism]

| Original post | Implementation |
|---|---|
| One call judges 25 people | 25 personas per `claude -p`; `--json-schema` pins that many verdicts in order, so parsing never breaks. |
| Opinion summary, not node-to-node | Round-1 verdicts are pure-aggregated, with no extra LLM call, into a summary fed to round 2, so cost is O(N), not O(N²). |
| No web app, no server | A Python script over local JSONL running the `claude` CLI as a subprocess. |

[Real runs]

| Run | Sample | Result | Cost |
|---|---|---|---|
| `kr_real_run` | 25 random Korean adults | 0% core_target, 4% adjacent, 96% not_applicable; round-2 flips 0/25 | $0.2183 |
| `kr_core_segment_run` | 17 = 12 `real_dataset` + 5 `illustrative_construction` | real rows 12/12 not_applicable; constructed 5/5 core_target + would_pay=yes | $0.1932 |
| Total | 2 runs x 2 rounds = 4 real calls | | $0.4115 |

Disclosure: the 5 `illustrative_construction` personas are not dataset rows — ideal users built by hand for IDEAINNOV's domains. Their 5/5 illustrates the pipeline, not a dataset finding, and is no substitute for interviews.

0 core_targets in a random 25 is not "the product is useless": probably well under 1% of the 1M rows are graduate-level engineering, materials or energy researchers. And it discriminates by domain, not credential — the lone `adjacent` persona, an IT researcher with a graduate degree, missed core_target because hardware reliability testing is no PDE domain. Holding an engineering job is not enough; core_target means someone who actually has to write a thesis or an SCI paper.

Objections beat price: advisor-funding dependence (₩25,000–30,000/mo), patent and security leak risk from uploading research data (₩50,000–130,000), and who verifies an AI draft's citations (₩120,000). Round 2 does move them — after the opinion summary the median max price fell from ₩50,000 to ₩45,000, and the mean from ₩71,000 to ₩52,000.

[Run]

```bash
# claude CLI installed and logged in
RUN="python3 harness/run_harness.py --product product/ideainnov.json --personas data/personas_kr_batch1.jsonl"
$RUN --out-dir results/dry_run --dry-run  # free, $0
$RUN --out-dir results/my_run             # 25 x 2 rounds = 2 calls, ~$0.22

# bigger sample (needs internet); --max-budget-usd caps spend
pip install datasets huggingface_hub pandas pyarrow
python3 data/prepare_personas.py --country Korea --n 2000 --slim --out data/personas_kr_2000.jsonl
# $0.109/25 people/round -> 2,000 people x 2 rounds ~ $17
```

[Known limitations]

- Cross-contamination: 25 personas share one context, so an earlier verdict may sway a later one despite the prompt forbidding it; ruling it out means shuffling order and re-running.
- Sample bias: the 25 came from offsets 0–25, not a shuffle, so the sample skews older; `prepare_personas.py`'s reservoir sampling would fix this given internet access.
- Proxy-mangled input: network limits forced the HF datasets-server API through a web proxy — of the rows retrieved, 15 came back as original Korean and 10 were paraphrased into English.

[License]

- Code: no license yet, all rights reserved until one is picked.
- Data: CC BY 4.0, per `data/ATTRIBUTION.md` and `.en.md`.
