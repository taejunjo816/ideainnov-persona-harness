#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_personas.py — production-scale sampler for the real NVIDIA
Nemotron-Personas datasets (CC BY 4.0), run on any machine with normal
internet access. (The seed batch data/personas_kr_batch1.jsonl was collected
differently, through the Hugging Face datasets-server REST API -- see
data/_seed_batch1_kr.py for that provenance.)

What this script does, at real scale:
  1. Reads the requested country's Nemotron-Personas parquet shards from the
     Hugging Face Hub. Two modes:
       --mode stream  : `datasets` streaming (no local file); fast, but fsspec's
                        block cache needs a few hundred MB of free memory.
       --mode shard   : downloads parquet shards to the HF cache on disk and
                        iterates them row-group by row-group with pyarrow
                        (low memory; works on machines where streaming raises
                        MemoryError). --max-shards limits how many of the 9
                        Korean shards are scanned (1 shard = ~111k rows).
       --mode auto    : (default) try stream, fall back to shard on
                        MemoryError / OSError.
  2. Draws a uniform random sample of --n rows (reservoir sampling, seeded).
  3. Optionally drops the verbose narrative fields (--slim) and keeps only
     the compact `persona` summary plus structured demographic fields --
     a trimmed, sampled subset is what keeps a multi-country pool small
     (tens of MB) instead of multi-GB raw files.
  4. Writes one flat JSONL file, schema-compatible with run_harness.py's
     load_personas().

No Hugging Face account is required (the datasets are public, not gated).
Setting HF_TOKEN (a free read token) only raises the anonymous rate limit.

Countries available in the nvidia/Nemotron-Personas collection (dataset id
suffix -> approx. size): USA (6M), Japan (6M), India (21M), Singapore (888k),
Brazil (6M), France (6M), Korea (7M underlying descriptions / 1M persona
rows), El Salvador (1M), Vietnam (600k), Belgium (300k).
https://huggingface.co/collections/nvidia/nemotron-personas

Install:
    pip install datasets huggingface_hub pandas pyarrow

Usage:
    python3 prepare_personas.py --country Korea --n 2000 --slim \\
        --out ../data/personas_kr_full_sample.jsonl
    # low-memory machine / Windows with a small pagefile:
    python3 prepare_personas.py --country Korea --n 200 --slim --mode shard --max-shards 1 \\
        --out ../data/personas_kr_200.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

# The harness never needs torch/tensorflow/jax. `datasets` imports them when
# they happen to be installed, and loading torch's CUDA DLLs can fail with
# "WinError 1455: paging file too small" on machines under memory pressure.
# Opt out before `datasets` is imported anywhere in this process.
for _v in ("USE_TORCH", "USE_TF", "USE_JAX"):
    os.environ.setdefault(_v, "0")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

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
    """Streaming path: no local file, but needs a few hundred MB of free memory."""
    from datasets import load_dataset  # pip install datasets
    ds = load_dataset(dataset_id, split="train", streaming=True)
    for row in ds:
        yield row


def iter_rows_via_shards(dataset_id: str, max_shards: int | None = None):
    """Low-memory path: download parquet shards to the local HF cache, then
    iterate them row-group by row-group with pyarrow (never holds a whole
    shard in RAM). Shards are scanned in order; use max_shards to bound
    download volume (1 Korean shard ~ 250 MB / ~111k rows)."""
    from huggingface_hub import HfApi, hf_hub_download  # pip install huggingface_hub
    import pyarrow.parquet as pq  # pip install pyarrow

    files = sorted(f for f in HfApi().list_repo_files(dataset_id, repo_type="dataset")
                   if f.endswith(".parquet"))
    if not files:
        raise RuntimeError(f"no parquet files found in {dataset_id}")
    if max_shards:
        files = files[:max_shards]
    for k, fname in enumerate(files, 1):
        print(f"  shard {k}/{len(files)}: {fname} (downloading to HF cache if needed)", file=sys.stderr)
        path = hf_hub_download(dataset_id, fname, repo_type="dataset")
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(batch_size=2000):
            for row in batch.to_pylist():
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
    ap.add_argument("--mode", choices=["auto", "stream", "shard"], default="auto",
                    help="stream = datasets streaming; shard = download parquet shards and read row-groups "
                         "(low memory); auto = stream, then fall back to shard on MemoryError/OSError")
    ap.add_argument("--max-shards", type=int, default=None,
                    help="shard mode: scan only the first K parquet shards (bounds download volume)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dataset_id = COUNTRY_TO_DATASET[args.country]
    country_code = {"Korea": "KR", "USA": "US", "Japan": "JP", "India": "IN",
                    "Singapore": "SG", "Brazil": "BR", "France": "FR",
                    "ElSalvador": "SV", "Vietnam": "VN", "Belgium": "BE"}[args.country]

    def run_stream():
        print(f"Streaming {dataset_id} and reservoir-sampling n={args.n} (seed={args.seed})...", file=sys.stderr)
        return reservoir_sample(iter_rows_via_datasets(dataset_id), args.n, args.seed)

    def run_shard():
        print(f"Shard mode: downloading {dataset_id} parquet shards"
              f"{' (max ' + str(args.max_shards) + ')' if args.max_shards else ''} "
              f"and reservoir-sampling n={args.n} (seed={args.seed})...", file=sys.stderr)
        return reservoir_sample(iter_rows_via_shards(dataset_id, args.max_shards), args.n, args.seed)

    try:
        if args.mode == "stream":
            sample = run_stream()
        elif args.mode == "shard":
            sample = run_shard()
        else:
            try:
                sample = run_stream()
            except (MemoryError, OSError) as e:
                print(f"WARNING: streaming failed ({type(e).__name__}: {str(e)[:120]}) -> "
                      f"falling back to shard mode (low memory).", file=sys.stderr)
                sample = run_shard()
    except ImportError as e:
        print(
            f"ERROR: missing dependency ({e}). Run:\n"
            "    pip install datasets huggingface_hub pandas pyarrow",
            file=sys.stderr,
        )
        return 1

    if not sample:
        print("ERROR: no rows sampled", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for i, row in enumerate(sample):
            rec = normalize(row, i, country_code, args.slim)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    size_mb = args.out.stat().st_size / (1024 * 1024)
    print(f"wrote {len(sample)} personas -> {args.out} ({size_mb:.1f} MB)", file=sys.stderr)
    print(
        "Tip: a trimmed (--slim) sample of a few thousand rows per country is "
        "only a few MB -- that is how a 10-country pool stays small.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
