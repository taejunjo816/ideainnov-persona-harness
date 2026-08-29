#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_personas.py — production-scale sampler for the real NVIDIA
Nemotron-Personas datasets, to be run somewhere with normal internet access
and `pip install` access (this sandboxed verification environment has
neither for huggingface.co / pypi.org, which is why data/personas_kr_batch1.jsonl
was instead seeded via the Hugging Face datasets-server REST API through a
web-fetch proxy -- see data/_seed_batch1_kr.py for that provenance).

What this script does, at real scale:
  1. Streams the requested country's Nemotron-Personas parquet file from the
     Hugging Face Hub (no need to materialize the full 1M-7M row / multi-GB
     file locally).
  2. Draws a stratified-ish random sample of --n rows (default 2000).
  3. Optionally drops the verbose narrative fields (--slim) and keeps only
     the compact `persona` summary plus structured demographic fields --
     this is almost certainly how the original post's harness got its full
     10-country pool down to ~63MB instead of multi-GB: a trimmed, sampled
     subset, not the raw released files.
  4. Writes one flat JSONL file, schema-compatible with run_harness.py's
     load_personas().

Countries available in the nvidia/Nemotron-Personas collection (dataset id
suffix -> approx. size): USA (6M), Japan (6M), India (21M), Singapore (888k),
Brazil (6M), France (6M), Korea (7M underlying descriptions / 1M persona
rows), El Salvador (1M), Vietnam (600k), Belgium (300k).
https://huggingface.co/collections/nvidia/nemotron-personas

Install (on a machine with real internet access):
    pip install datasets huggingface_hub pandas pyarrow

Usage:
    python3 prepare_personas.py --country Korea --n 2000 --slim \\
        --out ../data/personas_kr_full_sample.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

COUNTRY_TO_DATASET = {
    "Korea": "nvidia/Nemotron-Personas-Korea",
    "USA": "nvidia/Nemotron-Personas-USA",
    "Japan": "nvidia/Nemotron-Personas-Japan",
    "India": "nvidia/Nemotron-Personas-India",
    "Singapore": "nvidia/Nemotron-Personas-Singapore",
    "Brazil": "nvidia/Nemotron-Personas-Brazil",
    "France": "nvidia/Nemotron-Personas-France",
    "ElSalvador": "nvidia/Nemotron-Personas-ElSalvador",
    "Vietnam": "nvidia/Nemotron-Personas-Vietnam",
    "Belgium": "nvidia/Nemotron-Personas-Belgium",
}

# Fields kept in --slim mode (roughly matches persona_json_for_prompt() in
# run_harness.py, so the trimmed file is directly usable by the harness).
SLIM_FIELDS = [
    "uuid", "persona", "age", "sex", "occupation", "education_level",
    "bachelors_field", "province", "district", "family_type",
    "marital_status", "hobbies_and_interests_list", "career_goals_and_ambitions",
]


def iter_rows_via_datasets(dataset_id: str):
    """Preferred path: streaming load, no full download required."""
    from datasets import load_dataset  # pip install datasets
    ds = load_dataset(dataset_id, split="train", streaming=True)
    for row in ds:
        yield row


def reservoir_sample(rows, n: int, seed: int = 42) -> list[dict]:
    """Reservoir sampling so we can draw a uniform --n sample from a
    streaming dataset without knowing its length or loading it all into
    memory.
    """
    rng = random.Random(seed)
    sample: list[dict] = []
    for i, row in enumerate(rows):
        if i < n:
            sample.append(row)
        else:
            j = rng.randint(0, i)
            if j < n:
                sample[j] = row
    return sample


def normalize(row: dict, idx: int, country_code: str, slim: bool) -> dict:
    hobbies = row.get("hobbies_and_interests_list") or []
    if isinstance(hobbies, str):
        try:
            hobbies = json.loads(hobbies)
        except json.JSONDecodeError:
            hobbies = [hobbies]
    out = {
        "idx": idx,
        "persona_id": f"{country_code.lower()}_{idx:06d}",
        "uuid": row.get("uuid"),
        "persona": row.get("persona") or row.get("concise_persona") or "",
        "occupation": row.get("occupation"),
        "age": row.get("age"),
        "sex": row.get("sex"),
        "education_level": row.get("education_level"),
        "bachelors_field": row.get("bachelors_field"),
        "province": row.get("province"),
        "district": row.get("district"),
        "family_type": row.get("family_type"),
        "marital_status": row.get("marital_status"),
        "hobbies": hobbies,
        "career_goals": row.get("career_goals_and_ambitions") or "",
    }
    if not slim:
        for extra in ("professional_persona", "sports_persona", "arts_persona",
                       "travel_persona", "culinary_persona", "family_persona",
                       "cultural_background", "skills_and_expertise"):
            if extra in row:
                out[extra] = row[extra]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--country", choices=sorted(COUNTRY_TO_DATASET), default="Korea")
    ap.add_argument("--n", type=int, default=2000, help="sample size (default 2000)")
    ap.add_argument("--slim", action="store_true", help="drop verbose narrative fields to save space")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dataset_id = COUNTRY_TO_DATASET[args.country]
    country_code = {"Korea": "KR", "USA": "US", "Japan": "JP", "India": "IN",
                     "Singapore": "SG", "Brazil": "BR", "France": "FR",
                     "ElSalvador": "SV", "Vietnam": "VN", "Belgium": "BE"}[args.country]

    print(f"Streaming {dataset_id} and reservoir-sampling n={args.n} (seed={args.seed})...", file=sys.stderr)
    try:
        rows = iter_rows_via_datasets(dataset_id)
        sample = reservoir_sample(rows, args.n, args.seed)
    except ImportError:
        print(
            "ERROR: `datasets` is not installed. Run:\n"
            "    pip install datasets huggingface_hub pandas pyarrow\n"
            "on a machine with normal internet access (this is NOT expected "
            "to work inside the sandboxed verification environment).",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for i, row in enumerate(sample):
            rec = normalize(row, i, country_code, args.slim)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"wrote {len(sample)} personas -> {args.out} ({size_mb:.1f} MB)", file=sys.stderr)
    print(
        "Tip: the original harness's whole 10-country pool was ~63MB total "
        "(~6MB/country) -- that implies a similarly aggressive --n and "
        "--slim trim, not the raw multi-GB released files.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
