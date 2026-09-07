#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_copy_harness.py — synthetic-persona AD-COPY click-intent harness.

Sibling of `가상인구페르소나/ideainnov-persona-harness/harness/run_harness.py`,
same batch-of-25 mechanism, but the judgment target is different:

    sibling (run_harness.py):  personas judge a PRODUCT SPEC
                                -> would_use / user_type / would_pay
    this program:               personas judge ONE PIECE OF AD COPY
                                -> would_click / hook_phrase / blocker / trust

There is no round1/round2 "public opinion" broadcast here (that mechanism
belongs to the product-validation question, not to a single copy variant's
click-intent measurement) — each variant is evaluated ONCE against the
persona pool, batched 25 personas per `claude -p` call, exactly like the
sibling's round 1.

This module is meant to be used two ways:
  1. As its own CLI: evaluate one variant file against a persona file.
  2. As a library by ../optimize/evolve.py, which calls `run_variant()`
     directly (sequentially, once per variant per generation) instead of
     shelling out to this script N times.

Usage (standalone):
    python3 run_copy_harness.py \\
        --variant  ../copy/seed_variants.json#seed_01 \\
        --personas ../../가상인구페르소나/ideainnov-persona-harness/data/personas_kr_batch1.jsonl \\
        --out-dir  ../results/seed_01 \\
        --dry-run

--variant accepts either a path to a JSON file containing ONE variant
object {id, lang, headline, body, cta, angle, ...}, or `path.json#id` to
pull one variant by id out of a JSON file containing a list of variants
(e.g. copy/seed_variants.json).

Add --dry-run to exercise the entire pipeline (batching, validation,
aggregation, report) with a free, instant, deterministic stub instead of
real `claude` calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from copy_schemas import round_schema, validate_verdicts  # noqa: E402

SYSTEM_PROMPT_KO = (
    "당신은 광고 문구(홍보 카피)에 대한 합성 인구(synthetic population) 기반 "
    "클릭 의향(click intent) 시뮬레이션 엔진입니다. 입력으로 (1) 하나의 홍보 "
    "문구(headline/body/cta)와 (2) 페르소나 묶음이 주어집니다. 각 페르소나가 "
    "소셜미디어 피드에서 이 문구를 실제로 봤다고 가정하고, 나이/성별/직업/학력/"
    "전공/거주지/가족형태/취미/목표만 근거로 클릭 여부를 현실적으로 판단하세요.\n"
    "규칙:\n"
    "1) 각 페르소나는 서로 독립적으로 판단하십시오. 같은 배치 내 다른 페르소나의 "
    "판단에 영향받지 마세요 (교차 오염 금지).\n"
    "2) 과도하게 긍정적으로 평가하지 마세요. 문구가 아무리 매력적이어도 자신의 "
    "직업·관심사와 무관하면 다수는 no가 정상입니다. 학력이나 소득이 높다는 "
    "이유만으로 would_click을 yes로 올리지 마세요.\n"
    "3) hook_phrase는 주어진 문구(headline+body+cta) 안에 실제로 등장하는 어절만 "
    "인용하세요. 끌리는 부분이 없으면 빈 문자열(\"\")로 두세요. 문구에 없는 말을 "
    "지어내면 안 됩니다.\n"
    "4) blocker는 이 페르소나가 클릭을 망설이거나 거부하는 가장 구체적인 이유 "
    "한 문장입니다. 걸리는 게 없으면 빈 문자열(\"\")로 두세요.\n"
    "5) trust는 1~5 정수로, 이 문구가 과장·불신 없이 이 페르소나에게 신뢰가 가는 "
    "정도입니다 (1=전혀 신뢰 안 감, 5=매우 신뢰).\n"
    "6) 반드시 주어진 JSON 스키마로만 응답하고, 입력된 모든 페르소나에 대해 "
    "정확히 하나씩, 같은 순서로 verdict를 반환하세요.\n"
    "7) reasoning은 한 문장(약 15~25단어)으로, 그 페르소나 고유의 속성을 근거로 "
    "드세요."
)

SYSTEM_PROMPT_EN = (
    "You are a synthetic-population click-intent simulation engine for ad copy. "
    "You are given (1) one piece of ad copy (headline/body/cta) and (2) a batch "
    "of personas. Assume each persona actually saw this copy in their social "
    "media feed, and judge whether they would realistically click, using only "
    "their age/sex/occupation/education/field/region/family type/hobbies/goals.\n"
    "Rules:\n"
    "1) Judge each persona INDEPENDENTLY. Do not let one persona's judgment in "
    "this batch influence another's (no cross-contamination).\n"
    "2) Do not be overly generous. However appealing the copy sounds, most "
    "personas whose job/interests are unrelated should reasonably say no. "
    "Do not raise would_click to yes just because a persona has high education "
    "or income.\n"
    "3) hook_phrase must be a word/phrase that ACTUALLY appears in the given "
    "copy (headline+body+cta). If nothing hooked them, use an empty string "
    "(\"\"). Never invent wording that is not in the copy.\n"
    "4) blocker is one concrete sentence: the single biggest thing that makes "
    "this persona hesitate or refuse to click. Empty string (\"\") if none.\n"
    "5) trust is an integer 1-5: how credible this copy's claims feel to this "
    "persona, free of hype/distrust (1 = sounds fake, 5 = very credible).\n"
    "6) Respond ONLY in the given JSON schema, with exactly one verdict per "
    "persona given, in the same order.\n"
    "7) reasoning is one concise sentence (~15-25 words), grounded in THIS "
    "persona's own occupation/field/education/hobbies."
)


class HarnessError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_personas(path: Path) -> list[dict]:
    personas = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                personas.append(json.loads(line))
    return personas


def load_variant(spec: str) -> dict:
    """spec is either a bare path to a JSON file holding ONE variant object,
    or 'path.json#id' to pick one variant by id out of a JSON list/dict of
    variants (as produced by copy/seed_variants.json)."""
    if "#" in spec:
        path_str, wanted_id = spec.rsplit("#", 1)
    else:
        path_str, wanted_id = spec, None
    path = Path(path_str)
    if not path.exists():
        raise HarnessError(f"--variant file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if wanted_id is None:
        if isinstance(data, dict) and "id" in data:
            return data
        raise HarnessError(
            f"{path} does not contain a single variant object "
            f"(use path.json#id to select one from a list)"
        )

    items = data["variants"] if isinstance(data, dict) and "variants" in data else data
    if not isinstance(items, list):
        raise HarnessError(f"{path} is not a list of variants and no #id lookup is possible")
    for item in items:
        if item.get("id") == wanted_id:
            return item
    raise HarnessError(f"variant id {wanted_id!r} not found in {path}")


def chunked(seq: list, n: int) -> list[list]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def persona_json_for_prompt(p: dict) -> dict:
    """Trim to the fields the judge actually needs (keeps tokens down) —
    identical projection to the sibling harness's persona_json_for_prompt."""
    return {
        "persona_id": p["persona_id"],
        "persona": p.get("persona", ""),
        "age": p.get("age"),
        "sex": p.get("sex"),
        "occupation": p.get("occupation"),
        "education_level": p.get("education_level"),
        "bachelors_field": p.get("bachelors_field"),
        "region": f"{p.get('province', '')} {p.get('district', '')}".strip(),
        "family_type": p.get("family_type"),
        "hobbies": p.get("hobbies", []),
        "career_goals": p.get("career_goals", ""),
    }


def copy_brief(variant: dict) -> str:
    return (
        f"headline: {variant.get('headline', '')}\n"
        f"body: {variant.get('body', '')}\n"
        f"cta: {variant.get('cta', '')}\n"
        f"(angle: {variant.get('angle', '')})"
    )


# 캐시 접두부 정렬: 페르소나 블록(모든 변이에서 동일, 약 9k 토큰)을 앞에, 문구(약 100토큰)를
# 뒤에 둔다. 프롬프트 캐시는 접두부 단위로만 적중하므로 가변부가 앞에 있으면 매 호출마다
# 뒤 전체가 무효화된다. 순서를 바꿔도 판정 내용은 같다 — 과제 지시는 --system-prompt 에 있다.
# 캐시 접두부 정렬: 페르소나 블록(모든 변이에서 동일, 약 9k 토큰)을 앞에, 문구(약 100토큰)를
# 뒤에 둔다. 프롬프트 캐시는 접두부 단위로만 적중하므로 가변부가 앞에 있으면 매 호출마다
# 뒤 전체가 무효화된다. 순서를 바꿔도 판정 내용은 같다 — 과제 지시는 --system-prompt 에 있다.
def build_prompt(variant: dict, batch: list[dict], lang: str = "ko") -> str:
    payload = [persona_json_for_prompt(p) for p in batch]
    if lang == "en":
        return (
            f"[{len(batch)} personas — judge each independently]\n"
            f"{json.dumps(payload, ensure_ascii=False)}\n\n"
            f"[Ad copy — judge ONLY this one]\n{copy_brief(variant)}"
        )
    return (
        f"[페르소나 {len(batch)}명 — 각자 독립적으로 판단]\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"[홍보 문구 — 이 문구 하나만 판단 대상]\n{copy_brief(variant)}"
    )

# --------------------------------------------------------------------------
# The actual "1 call judges N personas" primitive
# --------------------------------------------------------------------------

_CLAUDE_BIN_CACHE = None


def resolve_claude_bin() -> str:
    """`claude` 실행 파일의 절대 경로를 찾는다.

    Windows에서 subprocess는 shell=False일 때 확장자 없는 "claude"를 해석하지 못해
    FileNotFoundError(WinError 2)로 죽는다(2026-09-01 유료 실행 1콜차에서 실측).
    또한 npm이 깔아두는 `claude.cmd` 배치 래퍼는 여러 줄 인자를 첫 행에서 잘라먹는
    알려진 문제가 있어(프로젝트 기록), 시스템 프롬프트/스키마처럼 개행이 든 인자를
    넘기는 이 하네스에서는 반드시 claude.exe 네이티브 바이너리를 써야 한다.
    그래서 .exe -> which() -> .cmd 순으로 탐색한다.
    """
    global _CLAUDE_BIN_CACHE
    if _CLAUDE_BIN_CACHE:
        return _CLAUDE_BIN_CACHE

    import glob as _glob
    import shutil as _shutil

    candidates = [
        os.environ.get("CLAUDE_BIN"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "node_modules",
                     "@anthropic-ai", "claude-code", "bin", "claude.exe"),
    ]
    candidates += sorted(_glob.glob(os.path.join(
        os.path.expanduser("~"), ".vscode", "extensions",
        "anthropic.claude-code-*", "resources", "native-binary", "claude.exe")), reverse=True)
    for c in candidates:
        if c and os.path.isfile(c):
            _CLAUDE_BIN_CACHE = c
            return c

    which = _shutil.which("claude.exe") or _shutil.which("claude")
    if which:
        _CLAUDE_BIN_CACHE = which
        return which
    raise HarnessError(
        "claude 실행 파일을 찾지 못했습니다. CLAUDE_BIN 환경변수에 claude.exe 절대경로를 지정하십시오.")


# Windows 기본 로케일이 cp949라 text=True 만 주면 claude 가 뱉는 UTF-8 한국어 JSON을
# 디코딩하다 UnicodeDecodeError 로 죽는다(2026-09-01 실측). encoding/errors 를 반드시 명시한다.
def call_claude_batch(
    system_prompt: str,
    user_prompt: str,
    schema: dict,
    model: str | None,
    max_budget_usd: float,
    timeout_s: int,
    retries: int = 1,
) -> tuple[dict, dict]:
    """Shell out to the `claude` CLI in headless (-p) mode with a JSON
    Schema so the CLI itself enforces structured output. Returns
    (structured_output, call_meta) where call_meta carries cost/timing for
    the audit trail. Identical pattern to the sibling harness."""
    # (실측 결함 2026-09-01) 프롬프트를 argv 로 넘기면 Windows CreateProcess 의
    # 명령줄 상한 32,767자에 걸려 FileNotFoundError [WinError 206] 로 죽는다.
    # 한국어 표본은 user 프롬프트가 13,304자라 통과했지만 미국 표본은 영문 서술이
    # 길어 35,903자가 되어 EN 트랙 첫 콜에서 즉사했다 — 한 언어의 통과가 다른
    # 언어의 통과를 보증하지 않는다. 프롬프트는 stdin 으로 넘겨 상한 자체를 없앤다
    # (argv 에는 스키마 1,396자 등 작은 것만 남는다).
    cmd = [
        resolve_claude_bin(), "-p",
"--system-prompt", system_prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--tools", "",
        # 판정과 무관한 컨텍스트 차단(2026-09-01 실측, 최소 프롬프트 기준):
        #   --strict-mcp-config  : --mcp-config 없이 주면 MCP 서버를 하나도 안 붙인다
        #                          (Gmail/Drive/Semrush/obsidian/telegram 스키마 약 33,900 토큰).
        #   --setting-sources "" : 설정 파일·CLAUDE.md 자동 발견을 끈다(약 21,000 토큰).
        #                          비용뿐 아니라 타당성 문제다 — 이 프로젝트 CLAUDE.md의 논문
        #                          작성 규칙이 광고 클릭 판정에 섞이면 안 된다.
        # 합계 74,759 -> 19,819 캐시 입력 토큰, $0.0575 -> $0.0105.
        "--strict-mcp-config",
        "--setting-sources", "",
        "--max-budget-usd", str(max_budget_usd),
    ]
    if model:
        cmd += ["--model", model]

    last_err = None
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  input=user_prompt, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            last_err = f"timeout after {timeout_s}s"
            continue
        if proc.returncode != 0 and not proc.stdout.strip():
            last_err = f"exit={proc.returncode} stderr={proc.stderr[:400]}"
            continue
        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError:
            last_err = f"non-JSON stdout: {proc.stdout[:400]}"
            continue
        if envelope.get("is_error"):
            last_err = f"claude reported error: {envelope.get('result')}"
            continue
        structured = envelope.get("structured_output")
        if structured is None:
            try:
                structured = json.loads(envelope.get("result", ""))
            except json.JSONDecodeError:
                last_err = f"no structured_output and result not JSON: {str(envelope.get('result'))[:400]}"
                continue
        meta = {
            "cost_usd": envelope.get("total_cost_usd"),
            "duration_ms": envelope.get("duration_ms"),
            "session_id": envelope.get("session_id"),
        }
        return structured, meta
    raise HarnessError(f"claude batch call failed after {retries + 1} attempt(s): {last_err}")


def dry_run_batch(variant: dict, batch: list[dict]) -> dict:
    """Free, instant, deterministic stand-in for call_claude_batch, seeded
    per (persona_id, variant content) so different variant TEXT produces
    different-but-reproducible verdicts (this is what lets the dry-run
    evolutionary loop in evolve.py show measurable score movement across
    generations without spending anything)."""
    variant_fingerprint = f"{variant.get('id','')}::{variant.get('headline','')}::{variant.get('body','')}::{variant.get('cta','')}"
    text_all = f"{variant.get('headline','')} {variant.get('body','')} {variant.get('cta','')}"
    lang = variant.get("lang", "ko")
    academic_kw = ("연구", "교수", "엔지니어", "박사", "대학원",
                    "research", "professor", "engineer", "phd", "scientist", "graduate")
    # crude content-aware nudges so mutated copy can measurably move the
    # score — NOT a claim of real predictive power, just enough dynamic
    # range to exercise evolve.py's ranking/mutation logic at $0.
    text_low = text_all.lower()
    authority_bonus = 0.10 if any(k in text_all for k in ("SCI", "심사위원", "검증", "reviewer", "review")) else 0.0
    free_bonus = 0.06 if ("무료" in text_all or "free" in text_low) else 0.0

    verdicts = []
    for p in batch:
        seed_str = f"{p['persona_id']}::{variant_fingerprint}"
        h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
        r = (h % 1000) / 1000.0
        persona_text_low = (p.get("occupation", "") + " " + p.get("bachelors_field", "")).lower()
        is_academic = any(k in persona_text_low for k in academic_kw)
        threshold = 0.55 - authority_bonus - free_bonus
        if is_academic:
            threshold -= 0.15
        would_click = "yes" if r < threshold * 0.4 else ("maybe" if r < threshold else "no")

        trust_h = int(hashlib.sha256((seed_str + "::trust").encode()).hexdigest(), 16)
        trust = 1 + (trust_h % 5)

        headline_words = [w for w in variant.get("headline", "").split() if w]
        hook_phrase = ""
        if would_click != "no" and headline_words:
            idx = (h // 1000) % len(headline_words)
            hook_phrase = headline_words[idx]

        blocker = ""
        if would_click != "yes":
            blocker = ("[dry-run stub] doesn't look related to my job/interests"
                       if lang == "en" else "[dry-run stub] 내 업무·관심사와 직접적인 관련이 없어 보임")

        verdicts.append({
            "persona_id": p["persona_id"],
            "would_click": would_click,
            "hook_phrase": hook_phrase,
            "blocker": blocker,
            "trust": trust,
            "reasoning": f"[dry-run stub for {p.get('occupation', '')}]",
        })
    return {"verdicts": verdicts}


# --------------------------------------------------------------------------
# Aggregation (plain arithmetic, no LLM call)
# --------------------------------------------------------------------------

def aggregate(verdicts: list[dict]) -> dict:
    n = len(verdicts)
    click_counts = Counter(v["would_click"] for v in verdicts)
    hooks = Counter(v["hook_phrase"] for v in verdicts if v.get("hook_phrase"))
    blockers = Counter(v["blocker"] for v in verdicts if v.get("blocker"))
    trusts = [v["trust"] for v in verdicts]
    return {
        "n": n,
        "would_click_pct": {k: round(100 * c / n, 2) for k, c in click_counts.items()} if n else {},
        "mean_trust": round(statistics.mean(trusts), 3) if trusts else 0.0,
        "top_hook_phrases": hooks.most_common(5),
        "top_blockers": blockers.most_common(5),
    }


# --------------------------------------------------------------------------
# Logging helper — writes to both stderr and out_dir/run.log
# --------------------------------------------------------------------------

class DualLogger:
    def __init__(self, log_path: Path, mode: str = "a"):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(log_path, mode, encoding="utf-8")

    def log(self, msg: str) -> None:
        print(msg, file=sys.stderr)
        self._fh.write(msg + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


# --------------------------------------------------------------------------
# Core: evaluate ONE variant against N personas
# --------------------------------------------------------------------------

def run_variant(
    variant: dict,
    personas: list[dict],
    batch_size: int,
    model: str | None,
    max_budget_usd: float,
    timeout_s: int,
    out_dir: Path,
    dry_run: bool,
    logger: DualLogger | None = None,
    repeats: int = 1,
) -> tuple[dict, list[dict]]:
    """Evaluate one variant against all personas (batched), write
    round_XX.json per batch + report.json + run.log into out_dir. Returns
    (report_dict, call_metas)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    own_logger = logger is None
    if own_logger:
        logger = DualLogger(out_dir / "run.log")

    variant.setdefault("lang", "ko")
    lang = variant.get("lang", "ko")
    system_prompt = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT_KO
    batches = chunked(personas, batch_size)
    all_verdicts: list[dict] = []
    call_metas: list[dict] = []

    logger.log(
        f"[variant {variant.get('id')}] lang={lang} {len(personas)} personas -> "
        f"{len(batches)} call(s) of up to {batch_size} (dry_run={dry_run})"
    )

    try:
        # (2026-09-02) 동일 문구 재판정 편차가 최대 7.84점으로 실측됐다. 텍스트가 한
        # 글자도 안 바뀐 변이가 세대를 넘어 재판정될 때 그만큼 흔들린다는 뜻이라,
        # 그보다 작은 점수 차이는 문구 차이인지 잡음인지 구별할 수 없다. 같은 문구를
        # repeats 회 판정해 평균 내면 표준오차가 sqrt(repeats) 배로 줄어든다.
        # repeats=1 이면 기존과 완전히 동일하게 동작한다(회귀 없음).
        for rep in range(max(1, repeats)):
         for i, batch in enumerate(batches):
             want_ids = {p["persona_id"] for p in batch}
             schema = round_schema(len(batch))
             t0 = time.time()
             if dry_run:
                 structured = dry_run_batch(variant, batch)
                 meta = {"cost_usd": 0.0, "duration_ms": 0, "session_id": "dry-run"}
             else:
                 structured, meta = call_claude_batch(
                     system_prompt, build_prompt(variant, batch, lang), schema,
                     model, max_budget_usd, timeout_s,
                 )
             elapsed = time.time() - t0

             verdicts = structured.get("verdicts") if isinstance(structured, dict) else None
             problems = validate_verdicts(verdicts, want_ids, len(batch))
             if problems:
                 raise HarnessError(
                     f"variant {variant.get('id')} batch {i}: invalid verdict payload "
                     f"({'; '.join(problems)})"
                 )

             round_path = out_dir / (f"round_{i:02d}.json" if repeats <= 1
                                     else f"round_r{rep:02d}_{i:02d}.json")
             with open(round_path, "w", encoding="utf-8") as f:
                 json.dump({
                     "variant_id": variant.get("id"), "batch_index": i, "repeat_index": rep,
                     "persona_ids": sorted(want_ids), "verdicts": verdicts, "call_meta": meta,
                 }, f, ensure_ascii=False, indent=2)

             cost_txt = f"${meta['cost_usd']:.4f}" if meta.get("cost_usd") is not None else "n/a"
             logger.log(
                 f"  batch {i}: {len(verdicts)} verdicts, cost={cost_txt}, "
                 f"wall={elapsed:.1f}s -> {round_path.name}"
             )
             all_verdicts.extend(verdicts)
             call_metas.append(meta)
    except HarnessError:
        if own_logger:
            logger.log("  ! HarnessError — aborting this variant, not writing report.json")
            logger.close()
        raise

    # 회차별로 따로 집계해 둔다. 평균만 남기면 이 문구의 판정이 얼마나 흔들렸는지
    # 사후에 알 수 없다 — 잡음 크기는 결과를 읽는 사람이 반드시 봐야 하는 값이다.
    per_repeat_stats = []
    if max(1, repeats) > 1:
        step = len(all_verdicts) // max(1, repeats)
        for r in range(max(1, repeats)):
            chunk = all_verdicts[r * step:(r + 1) * step]
            if chunk:
                per_repeat_stats.append({'repeat': r, **aggregate(chunk)})
    summary = aggregate(all_verdicts)
    total_cost = sum(m.get("cost_usd") or 0 for m in call_metas)
    report = {
        "variant_id": variant.get("id"),
        "variant": variant,
        "n_personas": len(personas),
        "batch_size": batch_size,
        "n_calls": len(call_metas),
        "repeats": max(1, repeats),
        "per_repeat": per_repeat_stats,
        "total_cost_usd": total_cost,
        "dry_run": dry_run,
        **summary,
    }
    with open(out_dir / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.log(
        f"[variant {variant.get('id')}] done. n={summary['n']} "
        f"would_click_pct={summary['would_click_pct']} mean_trust={summary['mean_trust']} "
        f"total_cost_usd={total_cost:.4f}"
    )
    if own_logger:
        logger.close()
    return report, call_metas


# --------------------------------------------------------------------------
# Main (standalone CLI)
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", required=True, help="path to a variant JSON file, or path.json#id")
    ap.add_argument("--personas", type=Path, required=True, help="JSONL file of personas")
    ap.add_argument("--out-dir", type=Path, required=True, help="directory to write round_*.json/report.json/run.log")
    ap.add_argument("--batch-size", type=int, default=25, help="personas judged per LLM call (default 25)")
    ap.add_argument("--model", default=None, help="passthrough to `claude --model` (default: account default)")
    ap.add_argument("--max-budget-usd", type=float, default=2.0, help="--max-budget-usd cap per batch call")
    ap.add_argument("--timeout-s", type=int, default=600, help="per-call subprocess timeout")

    ap.add_argument("--repeats", type=int, default=1,

                    help="같은 문구를 몇 번 판정할지. 판정 잡음(실측 최대 7.84점)을 줄이려면 3 이상. 비용도 배수로 늘어난다.")
    ap.add_argument("--dry-run", action="store_true", help="use a free deterministic stub instead of real claude calls")
    args = ap.parse_args()

    variant = load_variant(args.variant)
    personas = load_personas(args.personas)

    try:
        report, _ = run_variant(
            variant, personas, args.batch_size, args.model, args.max_budget_usd,
            args.timeout_s, args.out_dir, args.dry_run, repeats=args.repeats,
        )
    except HarnessError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
