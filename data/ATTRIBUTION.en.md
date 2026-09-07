English | [한국어](ATTRIBUTION.md)

[Data attribution]

The "real_dataset" persona rows in this repository come from NVIDIA's Nemotron-Personas datasets. Two samples are used, Korea and USA.

Korea sample

- Dataset: Nemotron-Personas-Korea
- Creator: NVIDIA
- Source: https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- Files: `personas_kr_batch1.jsonl`, `personas_kr_core_segment.jsonl`, `../copy-optimizer/data/personas_kr_25_filtered.jsonl`

USA sample

- Dataset: Nemotron-Personas-USA
- Creator: NVIDIA
- Source: https://huggingface.co/datasets/nvidia/Nemotron-Personas-USA
- License: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- File: `../copy-optimizer/data/personas_us_25_filtered.jsonl`

[Changes made]

Each original dataset has about 1 million rows. This repository includes only a tiny subset with a reduced set of fields.

The 15 rows in `personas_kr_batch1.jsonl` and all `real_dataset` rows in `personas_kr_core_segment.jsonl` were retrieved through the Hugging Face datasets-server API from a network-restricted environment. Some of those rows came back summarized or partially paraphrased into English. If you need the exact original text, re-collect it by reading the original parquet directly with `prepare_personas.py`.

The two filtered files under `copy-optimizer/data/` are 25 rows each, drawn from an 800-row pool by `filter_personas.py`. The filter keeps rows aged 22 or over that are in professional, research or technical work, or hold higher education, or studied a STEM field. Pass rates were 34.0 percent for Korea and 35.1 percent for the USA, and no minors survive the filter. The raw pass-rate output is in `_filter_stats_kr.json` and `_filter_stats_us.json` in the same folder.

The filter exists because a purely random sample contains rows that cannot judge an ad. The first row of the random USA sample was an infant aged 0. The filter deliberately does NOT narrow to people who obviously want the product, because that would make the judgment tautological. It stops at "adults an ad could plausibly reach".

[Rows that are NOT from these datasets]

The 5 rows marked `illustrative_construction` in `personas_kr_core_segment.jsonl` are not dataset rows. They are ideal-user personas constructed by hand for IDEAINNOV's domains. CC BY 4.0 attribution does not apply to them, but the marking must be preserved everywhere so they are never mistaken for real user data.

[Redistribution]

CC BY 4.0 permits redistribution and commercial use, provided attribution is given. If you publish or redistribute this repository, keep the attribution above (NVIDIA, dataset name, link, license).
