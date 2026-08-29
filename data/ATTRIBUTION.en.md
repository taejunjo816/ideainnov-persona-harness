**English** | [한국어](ATTRIBUTION.md)

# Data Attribution

The "real_dataset" persona rows in `data/personas_kr_batch1.jsonl` and
`data/personas_kr_core_segment.jsonl` in this repository were sourced from the following
dataset.

- **Dataset**: Nemotron-Personas-Korea
- **Creator**: NVIDIA
- **Source**: https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea
- **License**: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)
- **Changes made**: the original dataset has 1 million rows (about 2.0GB, 26 fields). This
  repository includes only a tiny subset (a few dozen rows) with a reduced set of fields. Some
  rows (15 rows in `personas_kr_batch1.jsonl`, and all `real_dataset` rows in
  `personas_kr_core_segment.jsonl`) were retrieved via the Hugging Face datasets-server API
  from a network-restricted environment, and some of those rows came back summarized or
  partially paraphrased into English in the process — if you need the exact original text,
  re-collect it by reading the original parquet directly with `data/prepare_personas.py`.
- **Not from this dataset**: the 5 rows marked `illustrative_construction` in
  `data/personas_kr_core_segment.jsonl` are not real dataset rows — they are example personas
  constructed directly by this project to match IDEAINNOV's target domains. They are not
  subject to the CC BY 4.0 attribution requirement, but this label must be preserved everywhere
  so they are never mistaken for real user data.

CC BY 4.0 freely permits redistribution and commercial use, subject to attribution. When
publishing or redistributing this repository, please retain the attribution above (NVIDIA,
dataset name, link, license).
