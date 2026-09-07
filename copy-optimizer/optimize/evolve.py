#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evolve.py — evolutionary ad-copy optimizer for ideainnov.com's promo copy,
using ../harness/run_copy_harness.py (synthetic-persona click-intent
judging) as the fitness function.

    score(variant) = w_yes*P(would_click=yes) + w_maybe*P(would_click=maybe)
                    + w_trust*mean(trust)
    defaults: w_yes=100, w_maybe=40, w_trust=8  (all CLI-overridable)

Generation 0 = the 18 seeds in copy/seed_variants_<lang>.json. Each
generation: evaluate every variant in the current population SEQUENTIALLY
(no parallel `claude` calls), rank by score, keep the top-3 elites. Call
`claude -p --json-schema` ONCE per generation to mutate: give it the
elites' text + their aggregated hook_phrase list + the losers' aggregated
blocker list, and ask for 5 new variants. Next generation's population =
3 elites + 5 children (population shrinks from 18 -> 8 after generation 0;
generation 0 is intentionally larger because that is the full research-
derived seed set).

Stops when --generations is reached, OR no score improvement for
--patience generations, OR --max-calls / --max-budget-usd is exhausted
(hard stop, checked BEFORE every paid call — never silently continues
past the cap).

LANGUAGE TRACKS (--lang ko|en|both, default both): Korean copy is judged
by the KR persona sample in Korean; English copy is judged by the US
persona sample (Nemotron-Personas-USA) in English. They are two entirely
independent evolutionary runs (own seeds, own personas, own elite pool,
own results/<lang>/ directory) — personas of one language never see copy
in the other language, and no batch ever mixes languages. When both run,
a comparison report is written to results/COMPARISON.md.

RESEARCH GATE (hard requirement): this script refuses to build a
population from stale research. Before anything else it checks
research/out/youtube_hooks.json: if it is missing, OR older than
--research-max-age-days (default 7), it AUTO-RUNS
`research/hook_research.py youtube` (conservative default --limit) to
regenerate it. If that auto-run itself fails (no network, yt-dlp
missing, ...), evolve.py fails loudly and tells you to run it manually —
it never silently proceeds on stale/absent research. Pass
--no-auto-research to make it refuse instead of auto-running.

COST PROJECTION: before the first paid call, this prints a conservative
estimate (documented in read_me / inline below) and hard-aborts if it
exceeds --max-budget-usd, so a `--generations` value that is too large
for the budget is caught before spending anything, not partway through.

Usage (free, no claude calls, exercises the whole pipeline):
    python3 evolve.py --generations 2 --dry-run --out-dir results/dryrun --lang both
"""
from __future__ import annotations

import argparse
import importlib.util
import collections
import json
import random
import statistics
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # 홍보문구최적화/
sys.path.insert(0, str(PROJECT_ROOT / "harness"))
sys.path.insert(0, str(PROJECT_ROOT / "research"))
import run_copy_harness  # noqa: E402

RESEARCH_FILE = PROJECT_ROOT / "research" / "out" / "youtube_hooks.json"
PRODUCTS_JSON = PROJECT_ROOT.parent / "common" / "products.json"

DEFAULT_PERSONAS_KO = (
    PROJECT_ROOT.parent / "가상인구페르소나" / "ideainnov-persona-harness" / "data" / "personas_kr_batch1.jsonl"
)
DEFAULT_PERSONAS_EN = PROJECT_ROOT / "data" / "personas_us_25.jsonl"


def _seeds_path(lang: str) -> Path:
    return PROJECT_ROOT / "copy" / f"seed_variants_{lang}.json"


# 이 환경에서 직접 측정한 1콜 단가(2026-09-01, 25명 배치 1콜, --strict-mcp-config +
# --setting-sources "" 적용 후): $0.4426, 소요 93초.
#
# 이전 값은 형제 하네스 README 의 $0.109 를 그대로 빌려온 것이었는데, 그 값은 이
# 환경에서 재현되지 않았다. 실제로는 MCP 툴 스키마와 CLAUDE.md 자동 로딩으로 매 콜
# 약 55,000 토큰이 더 실려 처음엔 $1.077, 플래그 정리 후 $0.4426 이 나왔다.
# 다른 곳에서 잰 단가를 이 환경의 단가라고 말하지 않는다 — 여기서 잰 값만 쓴다.
ASSUMED_COST_PER_CALL_USD = 0.4426
ASSUMED_COST_SOURCE = ("이 환경 실측 2026-09-01: 25명 배치 1콜 $0.4426 / 93초 "
                       "(results/_smoke4)")

# 세대당 콜 수 상한은 실제 시드 개수에서 계산한다(아래 project_cost 참조).
# 예전에는 18 로 하드코딩돼 있었는데 시드를 8개로 줄인 뒤에도 그대로 남아 있었다.
PROJECTION_MUTATION_CALLS_PER_GEN = 1

DEFAULT_MAX_BUDGET_USD = 15.0   # covers --lang both --generations 3 (~$12.4 projected) with headroom
DEFAULT_MAX_CALLS = 160         # matches the same envelope as a secondary hard cap
DEFAULT_PER_CALL_BUDGET_USD = 2.0
DEFAULT_GENERATIONS = 3
DEFAULT_PATIENCE = 2
DEFAULT_SEED = 42
DEFAULT_BATCH_SIZE = 25
DEFAULT_W_YES, DEFAULT_W_MAYBE, DEFAULT_W_TRUST = 100.0, 40.0, 8.0


class EvolveError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def actual_hook_type_mix(variants):
    """실제 변이 배열에서 훅 유형 분포를 직접 센다.

    (실측 결함, 2026-09-01) 이전에는 시드 JSON 안의 '_hook_type_taken' 메타데이터를
    그대로 인용했다. 18개 시드 파일을 8개로 줄이면서 그 메타데이터가 갱신되지 않아,
    실제로는 8개(숫자형2/질문형2/나머지 각1)를 평가하면서 리포트에는 18개(각 유형 3개)로
    적히는 거짓 보고가 만들어졌다. 같은 사실이 두 곳에 각자 기입돼 있으면 언젠가
    어긋난다 — 저장된 값을 믿지 말고 데이터에서 매번 센다.
    """
    return dict(collections.Counter(
        v.get('hook_type') or '미분류' for v in variants))


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# Scoring — THE ONE PLACE this formula is defined.
# --------------------------------------------------------------------------

def score(would_click_pct: dict, mean_trust: float,
          w_yes: float = DEFAULT_W_YES, w_maybe: float = DEFAULT_W_MAYBE,
          w_trust: float = DEFAULT_W_TRUST) -> float:
    p_yes = (would_click_pct.get("yes", 0.0)) / 100.0
    p_maybe = (would_click_pct.get("maybe", 0.0)) / 100.0
    return w_yes * p_yes + w_maybe * p_maybe + w_trust * mean_trust


# --------------------------------------------------------------------------
# Research gate: hard-require fresh research, auto-run if missing/stale.
# --------------------------------------------------------------------------

def _load_hook_research_module():
    path = PROJECT_ROOT / "research" / "hook_research.py"
    spec = importlib.util.spec_from_file_location("hook_research", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ensure_research_fresh(max_age_days: float, auto_limit: int, auto: bool) -> None:
    if RESEARCH_FILE.exists():
        age_days = (time.time() - RESEARCH_FILE.stat().st_mtime) / 86400
        if age_days <= max_age_days:
            log(f"[research-gate] {RESEARCH_FILE.name} OK (age {age_days:.2f}d <= {max_age_days}d)")
            return
        log(f"[research-gate] {RESEARCH_FILE.name} STALE (age {age_days:.2f}d > {max_age_days}d)")
    else:
        log(f"[research-gate] {RESEARCH_FILE} MISSING")

    if not auto:
        raise EvolveError(
            f"research/out/youtube_hooks.json missing/stale and --no-auto-research was set.\n"
            f"  Run first:  python research/hook_research.py youtube"
        )

    log(f"[research-gate] auto-running `hook_research.py youtube --limit {auto_limit}` "
        f"(this is free — yt-dlp search, no claude calls) ...")
    hr = _load_hook_research_module()

    class _Args:
        pass
    a = _Args()
    a.queries = str(PROJECT_ROOT / "research" / "queries.json")
    a.limit = auto_limit
    a.timeout_s = 600
    a.refresh = False
    a.use_llm = False
    a.model = None
    a.max_budget_usd = 1.0
    try:
        rc = hr.cmd_youtube(a)
    except hr.ResearchError as e:
        raise EvolveError(f"auto-run of `hook_research.py youtube` failed: {e}\n"
                           f"  Run it manually and inspect the error: python research/hook_research.py youtube")
    if rc != 0:
        raise EvolveError("auto-run of `hook_research.py youtube` returned non-zero. "
                           "Run it manually: python research/hook_research.py youtube")
    log("[research-gate] auto-run complete, youtube_hooks.json refreshed.")


def ensure_seeds_available(lang: str, auto: bool) -> None:
    seeds_path = _seeds_path(lang)
    if seeds_path.exists():
        if RESEARCH_FILE.exists() and seeds_path.stat().st_mtime < RESEARCH_FILE.stat().st_mtime:
            log(f"[research-gate] WARNING: {seeds_path.name} is older than youtube_hooks.json — "
                f"consider `python research/hook_research.py seeds --lang {lang}` to refresh it. "
                f"Continuing with the existing file (not auto-overwritten).")
        return
    if not auto:
        raise EvolveError(f"{seeds_path} does not exist and --no-auto-research was set.\n"
                           f"  Run first:  python research/hook_research.py seeds --lang {lang}")
    log(f"[research-gate] {seeds_path.name} missing -> auto-running "
        f"`hook_research.py seeds --lang {lang}` ...")
    hr = _load_hook_research_module()

    class _Args:
        pass
    a = _Args()
    a.lang = lang
    try:
        rc = hr.cmd_seeds(a)
    except hr.ResearchError as e:
        raise EvolveError(f"auto-run of `hook_research.py seeds --lang {lang}` failed: {e}")
    if rc != 0:
        raise EvolveError(f"auto-run of `hook_research.py seeds --lang {lang}` returned non-zero.")


# --------------------------------------------------------------------------
# Budget tracking — hard stop, checked BEFORE every paid call.
# --------------------------------------------------------------------------

class BudgetTracker:
    def __init__(self, max_budget_usd: float | None, max_calls: int | None):
        self.max_budget_usd = max_budget_usd
        self.max_calls = max_calls
        self.total_cost = 0.0
        self.total_calls = 0

    def register(self, cost_usd: float | None, n_calls: int = 1) -> None:
        self.total_cost += cost_usd or 0.0
        self.total_calls += n_calls

    def check_before_call(self, dry_run: bool) -> str | None:
        """Returns a stop-reason string if the NEXT call must not happen."""
        if self.max_calls is not None and self.total_calls >= self.max_calls:
            return "max_calls_exhausted"
        if not dry_run and self.max_budget_usd is not None and self.total_cost >= self.max_budget_usd:
            return "max_budget_exhausted"
        return None


# --------------------------------------------------------------------------
# Mutation (real + dry-run stub)
# --------------------------------------------------------------------------

def mutate_schema(n: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "variants": {
                "type": "array", "minItems": n, "maxItems": n,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "headline": {"type": "string", "maxLength": 40},
                        "body": {"type": "string", "maxLength": 120},
                        "cta": {"type": "string", "maxLength": 20},
                        "angle": {"type": "string"},
                    },
                    "required": ["id", "headline", "body", "cta", "angle"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["variants"],
        "additionalProperties": False,
    }


def _products_fact_sheet(lang: str, products: dict) -> str:
    lines = []
    for key, prog in products.get("programs", {}).items():
        if lang == "en":
            name = prog.get("name_en", key)
            facts = list(prog.get("differentiators_en", []))
            if prog.get("pain_en"):
                facts.append(f"pain point: {prog['pain_en']}")
            for h in prog.get("hooks_en", {}).get("thread", []):
                facts.append(h)
        else:
            name = prog.get("name_ko", key)
            facts = list(prog.get("features", []))
            if prog.get("price_ko"):
                facts.append(f"가격: {prog['price_ko']}")
        lines.append(f"- {name}: " + " / ".join(facts))
    return "\n".join(lines)


def _forbidden_words_sheet(lang: str, products: dict) -> str:
    words = list(products.get("forbidden_words_global", []))
    for prog in products.get("programs", {}).values():
        words += prog.get("forbidden_words", [])
    label = "Forbidden phrases (never use)" if lang == "en" else "금지 표현(사용 금지)"
    return f"{label}: " + ", ".join(sorted(set(words)))


MUTATE_SYSTEM_PROMPT_KO = (
    "당신은 홍보 문구(광고 카피) 진화 최적화 엔진입니다. 성과가 좋았던 문구(엘리트)의 "
    "텍스트와, 그 문구들에서 사람들이 실제로 끌렸던 어절(hook_phrase), 그리고 성과가 "
    "낮았던 문구들의 걸림돌(blocker)이 주어집니다. 엘리트의 장점을 유지하면서 걸림돌을 "
    "해소한 새로운 홍보 문구 5개를 제안하세요.\n"
    "규칙:\n"
    "1) 모든 주장은 반드시 아래 '제품 사실' 목록에 있는 내용에만 근거해야 합니다. "
    "목록에 없는 숫자나 기능, 가격을 지어내면 안 됩니다.\n"
    "2) 아래 금지 표현은 절대 포함하지 마세요.\n"
    "3) headline은 40자, body는 120자, cta는 20자를 넘지 마세요.\n"
    "4) 반드시 주어진 JSON 스키마로만 응답하고, 정확히 5개의 variants를 반환하세요."
)

MUTATE_SYSTEM_PROMPT_EN = (
    "You are an ad-copy evolutionary optimization engine. You are given the "
    "text of high-performing copy (elites), the word/phrase people actually "
    "hooked onto in that copy (hook_phrase), and the biggest blockers in "
    "low-performing copy. Propose 5 new pieces of ad copy that keep what "
    "worked in the elites while addressing the blockers.\n"
    "Rules:\n"
    "1) Every claim must be grounded ONLY in the 'product facts' list below. "
    "Never invent a number, feature, or price not in that list.\n"
    "2) Never include any of the forbidden phrases below.\n"
    "3) headline <= 40 chars, body <= 120 chars, cta <= 20 chars.\n"
    "4) Respond ONLY in the given JSON schema, with exactly 5 variants."
)


def dry_run_mutate(elites: list[dict], hook_phrases: list[str], blockers: list[str],
                    rng: random.Random, gen_idx: int, lang: str, n: int = 5) -> list[dict]:
    """Free, deterministic (seeded via `rng`) stand-in for the real mutation
    call — lets the whole evolutionary loop be exercised at $0. NOT a claim
    of real copy-generation quality."""
    children = []
    for i in range(n):
        base = elites[i % len(elites)]
        hp = hook_phrases[rng.randrange(len(hook_phrases))] if hook_phrases else ""
        bl = blockers[rng.randrange(len(blockers))] if blockers else ""
        headline = base["headline"]
        if hp and hp not in headline:
            suffix = f" ({hp})"
            if len(headline) + len(suffix) <= 40:
                headline = headline + suffix
        body = base["body"]
        if bl:
            note = f" ({bl} 아님)" if lang == "ko" else f" (not: {bl})"
            if len(body) + len(note) <= 120:
                body = body + note
        children.append({
            "id": f"gen{gen_idx:02d}_{lang}_child{i + 1}",
            "lang": lang,
            "headline": headline[:40],
            "body": body[:120],
            "cta": base["cta"],
            "angle": f"{base.get('angle', '')}+mut",
            "hook_type": base.get("hook_type"),
            "hook_template": base.get("hook_template"),
            "source_evidence": f"[dry-run stub] mutated from {base['id']}",
            "evidence": base.get("evidence", []),
            "products_program": base.get("products_program"),
        })
    return children


def call_mutation(elites: list[dict], hook_phrases: list[str], blockers: list[str],
                   lang: str, products: dict, model: str | None, max_budget_usd: float,
                   timeout_s: int, gen_idx: int) -> tuple[list[dict], dict]:
    sys_prompt = MUTATE_SYSTEM_PROMPT_EN if lang == "en" else MUTATE_SYSTEM_PROMPT_KO
    elites_text = "\n".join(
        f"- [{v['id']}] headline={v['headline']!r} body={v['body']!r} cta={v['cta']!r} angle={v.get('angle', '')}"
        for v in elites
    )
    user_prompt = (
        f"[Elites]\n{elites_text}\n\n"
        f"[hook_phrase observed]\n{json.dumps(hook_phrases, ensure_ascii=False)}\n\n"
        f"[blockers observed in low performers]\n{json.dumps(blockers, ensure_ascii=False)}\n\n"
        f"[Product facts — the ONLY allowed source of claims]\n{_products_fact_sheet(lang, products)}\n\n"
        f"[{_forbidden_words_sheet(lang, products)}]"
    )
    import subprocess
    # (실측 결함 2026-09-01) 프롬프트를 argv 로 넘기면 Windows CreateProcess 의
    # 명령줄 상한 32,767자에 걸려 FileNotFoundError [WinError 206] 로 죽는다.
    # 한국어 표본은 user 프롬프트가 13,304자라 통과했지만 미국 표본은 영문 서술이
    # 길어 35,903자가 되어 EN 트랙 첫 콜에서 즉사했다 — 한 언어의 통과가 다른
    # 언어의 통과를 보증하지 않는다. 프롬프트는 stdin 으로 넘겨 상한 자체를 없앤다
    # (argv 에는 스키마 1,396자 등 작은 것만 남는다).
    cmd = [
        # (실측 결함) 여기가 bare "claude" 였다. 세대 경계에서만 실행되는 경로라
        # 세대 0에서 죽은 1차 실행은 이 지점에 도달조차 못했고, 하네스 쪽만 고치고
        # 끝냈다면 세대 1에서 WinError 2 로 같은 죽음을 반복했을 것이다.
        run_copy_harness.resolve_claude_bin(), "-p",
"--system-prompt", sys_prompt,
        "--output-format", "json", "--json-schema", json.dumps(mutate_schema(5), ensure_ascii=False),
        "--tools", "",
        # 하네스와 동일하게 무관 컨텍스트를 차단한다. 비용(약 55k 토큰)뿐 아니라
        # 타당성 문제 — 이 프로젝트 CLAUDE.md 의 학술 논문 작성 금지 규칙이
        # 광고 문구를 생성하는 호출에 섞여서는 안 된다.
        "--strict-mcp-config",
        "--setting-sources", "",
        "--max-budget-usd", str(max_budget_usd),
    ]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  input=user_prompt, timeout=timeout_s)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise EvolveError(f"mutation call failed: exit={proc.returncode} stderr={proc.stderr[:400]!r}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise EvolveError(f"mutation call reported error: {envelope.get('result')}")
    structured = envelope.get("structured_output") or json.loads(envelope.get("result", "{}"))
    variants = structured.get("variants", [])
    if len(variants) != 5:
        raise EvolveError(f"mutation call returned {len(variants)} variants, expected 5")
    for i, v in enumerate(variants):
        v["id"] = f"gen{gen_idx:02d}_{lang}_{v.get('id') or f'child{i + 1}'}"
        v["lang"] = lang
        v.setdefault("hook_type", None)
        v.setdefault("hook_template", None)
        v["source_evidence"] = "mutated by claude -p (see mutation_call.json for prompt/inputs)"
        v.setdefault("evidence", [])
        v.setdefault("products_program", None)
    meta = {"cost_usd": envelope.get("total_cost_usd"), "duration_ms": envelope.get("duration_ms")}
    return variants, meta


# --------------------------------------------------------------------------
# One full evolutionary run for ONE language
# --------------------------------------------------------------------------

def load_resume_population(resume_dir: Path, lang: str) -> tuple[list, int]:
    """이전 실행의 최종 엘리트를 개체군으로 되살린다.

    왜 엘리트인가: 진화 루프가 세대마다 남기는 것이 top-3 엘리트다. 시드로 되돌아가면
    이미 지불한 세대가 통째로 버려지고, LLM 판정은 결정론이 아니라서 같은 seed 로도
    같은 점수가 나오지 않는다. 즉 '재현'이 아니라 그냥 다른 실행이 된다.

    반환: (개체군, 다음 세대 번호, 이전 실행이 집계한 blocker 목록)
    """
    rep = resume_dir / lang / "FINAL_REPORT.json"
    if not rep.exists():
        raise EvolveError(f"이어받을 리포트가 없습니다: {rep}")
    prev = load_json(rep)
    elites = prev.get("final_elites") or []
    if not elites:
        raise EvolveError(f"{rep} 에 final_elites 가 비어 있어 이어받을 수 없습니다.")
    last_gen = -1
    for row in (prev.get("score_progression") or []):
        try:
            last_gen = max(last_gen, int(row.get("generation", -1)))
        except (TypeError, ValueError):
            pass
    # 우승 문구가 엘리트 목록에 없으면(이전 세대에서 나온 최고점) 함께 넣는다.
    win = prev.get("winning_variant")
    ids = {v.get("id") for v in elites}
    if win and win.get("id") not in ids:
        elites = [win] + elites
    blockers = [b for b, _ in (prev.get("top_blockers_overall") or []) if b]
    return [dict(v) for v in elites], last_gen + 1, blockers


def run_language(lang: str, args, personas_path: Path, out_root: Path,
                  rng: random.Random, budget: BudgetTracker, products: dict) -> dict:
    resume_dir = getattr(args, "resume_from", None)
    if resume_dir:
        population, auto_offset, resume_blockers = load_resume_population(resume_dir, lang)
        gen_start = args.gen_offset if args.gen_offset is not None else auto_offset
        log(f"[{lang}] 이어받기: {resume_dir} 의 최종 엘리트 {len(population)}개로 "
            f"세대 {gen_start} 부터 계속합니다(시드에서 재시작하지 않습니다).")
    else:
        population = load_seeds_list(lang)   # 개수·구성의 단일 소스
        resume_blockers = []
        gen_start = args.gen_offset if args.gen_offset is not None else 0
    # population 은 세대마다 교체되므로, 최종 리포트가 '세대 0 시드 구성'을 말하려면
    # 원본을 따로 붙잡아 둬야 한다. 세대 1의 개체군을 시드라고 보고하면 또 거짓말이 된다.
    seed_population = list(population)
    personas = run_copy_harness.load_personas(personas_path)
    log(f"[{lang}] {len(population)} seed variants x {len(personas)} personas "
        f"(seed hook-type mix: {actual_hook_type_mix(population)})")

    best_ever = None
    best_ever_score = float("-inf")
    stall = 0
    score_progression = []
    all_hook_phrases = Counter()
    all_blockers = Counter()
    stopped_reason = "generations_reached"
    final_elites: list[dict] = []
    cost_before = budget.total_cost
    calls_before = budget.total_calls

    gen = gen_start
    while gen < gen_start + args.generations:
        stop = budget.check_before_call(args.dry_run)
        if stop:
            stopped_reason = stop
            log(f"[{lang}] HARD STOP before generation {gen}: {stop} "
                f"(total_cost=${budget.total_cost:.4f}, total_calls={budget.total_calls})")
            break

        gen_dir = out_root / f"gen_{gen:02d}"
        scored = []
        aborted_mid_gen = False
        for variant in population:
            stop = budget.check_before_call(args.dry_run)
            if stop:
                stopped_reason = stop
                log(f"[{lang}] HARD STOP mid-generation {gen} before evaluating "
                    f"{variant.get('id')}: {stop}")
                aborted_mid_gen = True
                break
            v_out_dir = gen_dir / variant["id"]
            report, call_metas = run_copy_harness.run_variant(
                variant, personas, args.batch_size, args.model, args.per_call_budget_usd,
                args.timeout_s, v_out_dir, args.dry_run, repeats=args.repeats,
            )
            for m in call_metas:
                budget.register(m.get("cost_usd"), 1)
            s = score(report["would_click_pct"], report["mean_trust"], args.w_yes, args.w_maybe, args.w_trust)
            scored.append((s, variant, report))
            for phrase, c in report.get("top_hook_phrases", []):
                if phrase:
                    all_hook_phrases[phrase] += c
            for blocker, c in report.get("top_blockers", []):
                if blocker:
                    all_blockers[blocker] += c

        if aborted_mid_gen:
            break
        if not scored:
            break

        rng.shuffle(scored)  # seeded tie-break shuffle before stable score-sort
        scored.sort(key=lambda t: t[0], reverse=True)

        gen_best_score = scored[0][0]
        gen_mean_score = statistics.mean(s for s, _, _ in scored)
        score_progression.append({
            "generation": gen, "population_size": len(scored),
            "best_score": round(gen_best_score, 3), "best_variant_id": scored[0][1]["id"],
            "mean_score": round(gen_mean_score, 3),
        })
        elites_this_gen = [v for _, v, _ in scored[:3]]
        final_elites = elites_this_gen
        dump_json(gen_dir / "gen_summary.json", {
            "generation": gen, "ranking": [
                {"variant_id": v["id"], "score": round(s, 3), "hook_type": v.get("hook_type"),
                 "headline": v["headline"]} for s, v, _ in scored
            ],
            "elites": [v["id"] for v in elites_this_gen],
        })

        if gen_best_score > best_ever_score + 1e-9:
            best_ever_score = gen_best_score
            best_ever = {"variant": scored[0][1], "report": scored[0][2],
                          "score": gen_best_score, "generation": gen}
            stall = 0
        else:
            stall += 1

        gen += 1
        if gen >= gen_start + args.generations:
            # (실측 결함 2026-09-01) 여기가 args.generations 만 보고 있었다. while 조건만
            # offset 기준으로 고치고 이 break 를 놓쳐, 이어받기 시 2세대 요청이 1세대만
            # 돌았다. 무료 드라이런이 아니었으면 유료로 반만 돌고 끝났을 결함이다.
            break  # 요청한 세대 수를 채웠다
        if stall >= args.patience:
            stopped_reason = "patience_exhausted"
            log(f"[{lang}] stopping: no score improvement for {args.patience} generation(s)")
            break

        stop = budget.check_before_call(args.dry_run)
        if stop:
            stopped_reason = stop
            log(f"[{lang}] HARD STOP before mutation call for generation {gen}: {stop}")
            break

        losers = scored[3:]
        hook_phrase_pool = [p for _, v, r in scored[:3] for p, _ in r.get("top_hook_phrases", []) if p]
        blocker_pool = [b for _, v, r in losers for b, _ in r.get("top_blockers", []) if b]
        if not blocker_pool and resume_blockers:
            # 이어받기 첫 세대는 개체군이 엘리트뿐이라 losers 가 비고, 그러면 돌연변이가
            # '무엇이 걸렸는가' 신호 없이 문구를 만든다. 이전 실행이 집계해 둔 blocker 를
            # 대신 넣는다 — 같은 표본, 같은 제품이므로 유효한 신호다.
            blocker_pool = list(resume_blockers)
        sampled_blockers = rng.sample(blocker_pool, min(len(blocker_pool), 8)) if blocker_pool else []
        elites_shuffled = list(elites_this_gen)
        rng.shuffle(elites_shuffled)

        if args.dry_run:
            children = dry_run_mutate(elites_shuffled, hook_phrase_pool, sampled_blockers, rng, gen, lang)
            mutation_meta = {"cost_usd": 0.0, "dry_run": True}
        else:
            children, mutation_meta = call_mutation(
                elites_shuffled, hook_phrase_pool, sampled_blockers, lang, products,
                args.model, args.per_call_budget_usd, args.timeout_s, gen,
            )
        budget.register(mutation_meta.get("cost_usd"), 1)
        dump_json(gen_dir / "mutation_call.json", {
            "elites": [v["id"] for v in elites_shuffled],
            "hook_phrases_sampled": hook_phrase_pool[:20],
            "blockers_sampled": sampled_blockers,
            "children": children, "meta": mutation_meta,
        })
        population = elites_this_gen + children

    lang_cost = budget.total_cost - cost_before
    lang_calls = budget.total_calls - calls_before

    final = {
        "lang": lang,
        "seed": args.seed,
        "generations_requested": args.generations,
        "generations_run": len(score_progression),
        "stopped_reason": stopped_reason,
        "weights": {"w_yes": args.w_yes, "w_maybe": args.w_maybe, "w_trust": args.w_trust},
        "winning_variant": (best_ever["variant"] if best_ever else None),
        "winning_score": (round(best_ever["score"], 3) if best_ever else None),
        "winning_generation": (best_ever["generation"] if best_ever else None),
        "winning_report": (best_ever["report"] if best_ever else None),
        "score_progression": score_progression,
        "top_hook_phrases_overall": all_hook_phrases.most_common(5),
        "top_blockers_overall": all_blockers.most_common(5),
        "final_elites": final_elites,
        "total_calls_this_lang": lang_calls,
        "total_cost_usd_this_lang": round(lang_cost, 4),
        "dry_run": args.dry_run,
        "seed_hook_type_mix": actual_hook_type_mix(seed_population),
        # 이어받기 실행이면 위 구성은 시드가 아니라 물려받은 엘리트다. 라벨만 보고
        # "이 실행이 이 시드로 시작했다"고 오해하지 않도록 출처를 함께 남긴다.
        "population_origin": ("resumed_elites:" + str(resume_dir) if resume_dir else "seed_file"),
        "generation_start": gen_start,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    dump_json(out_root / "FINAL_REPORT.json", final)
    (out_root / "FINAL_REPORT.md").write_text(render_final_report_md(final), encoding="utf-8")
    log(f"[{lang}] done. stopped_reason={stopped_reason} generations_run={len(score_progression)} "
        f"winning_score={final['winning_score']} this_lang_cost=${lang_cost:.4f} calls={lang_calls}")
    return final


# --------------------------------------------------------------------------
# Reports
# --------------------------------------------------------------------------

def render_final_report_md(final: dict) -> str:
    lang_label = "한국어(KO)" if final["lang"] == "ko" else "English(EN)"
    lines = [
        f"[홍보 문구 진화 최적화 — {lang_label} 최종 리포트]",
        "",
        "중요(정직 고지): 이 점수는 합성 페르소나(AI 시뮬레이션)가 예측한 시뮬레이션 클릭 의향이며, "
        "실제 광고의 클릭률(CTR)이 아닙니다. 표본에 `illustrative_construction`(직접 구성한 예시) 페르소나가 "
        "섞여 있다면 그 사실도 함께 밝혀야 합니다 — 이 실행의 표본 출처는 아래 참고.",
        "",
        f"- seed: {final['seed']} (재현 가능 — 동일 seed는 동일 결과)",
        f"- 요청한 세대 수: {final['generations_requested']} / 실제 실행된 세대 수: {final['generations_run']}",
        f"- 종료 사유(stopped_reason): {final['stopped_reason']}",
        f"- 점수 가중치: yes={final['weights']['w_yes']}, maybe={final['weights']['w_maybe']}, "
        f"trust={final['weights']['w_trust']}  (score = w_yes*P(yes) + w_maybe*P(maybe) + w_trust*mean(trust))",
        f"- 이 언어 트랙 호출 수: {final['total_calls_this_lang']}, 비용: ${final['total_cost_usd_this_lang']:.4f} "
        f"(dry_run={final['dry_run']})",
        f"- 세대 0 시드의 훅 유형 구성: {final.get('seed_hook_type_mix')}",
        "",
        "[우승 문구]",
        "",
    ]
    w = final.get("winning_variant")
    if w:
        lines += [
            f"- id: `{w['id']}` (세대 {final['winning_generation']}, score={final['winning_score']})",
            f"- hook_type: {w.get('hook_type')} / hook_template: {w.get('hook_template')}",
            f"- headline: {w['headline']}",
            f"- body: {w['body']}",
            f"- cta: {w['cta']}",
            f"- angle: {w.get('angle')}",
            f"- source_evidence: {w.get('source_evidence')}",
            f"- products.json evidence: {w.get('evidence')}",
        ]
        wr = final.get("winning_report") or {}
        if wr:
            lines += [
                "",
                f"- 판정 결과: would_click_pct={wr.get('would_click_pct')}, "
                f"mean_trust={wr.get('mean_trust')}, n={wr.get('n')}",
            ]
    else:
        lines.append("(예산/호출 한도로 인해 어떤 세대도 완료되지 못해 우승 문구가 없습니다.)")

    lines += ["", "[세대별 점수 추이]", "", "| 세대 | 개체 수 | 최고 점수 | 최고 개체 | 평균 점수 |",
              "|---:|---:|---:|---|---:|"]
    for row in final["score_progression"]:
        lines.append(f"| {row['generation']} | {row['population_size']} | {row['best_score']} | "
                      f"`{row['best_variant_id']}` | {row['mean_score']} |")

    lines += ["", "[전체 세대 통틀어 상위 hook_phrase 5]", ""]
    if final["top_hook_phrases_overall"]:
        for phrase, c in final["top_hook_phrases_overall"]:
            lines.append(f"- '{phrase}' ({c}회)")
    else:
        lines.append("(관측된 hook_phrase 없음)")

    lines += ["", "[전체 세대 통틀어 상위 blocker 5]", ""]
    if final["top_blockers_overall"]:
        for blocker, c in final["top_blockers_overall"]:
            lines.append(f"- {blocker} ({c}회)")
    else:
        lines.append("(관측된 blocker 없음)")

    lines += ["", "[최종 세대 엘리트(top-3)]", ""]
    for v in final.get("final_elites", []):
        lines.append(f"- `{v['id']}` [{v.get('hook_type')}] {v['headline']}")
    lines.append("")
    return "\n".join(lines)


def render_comparison_md(ko_final: dict, en_final: dict) -> str:
    lines = [
        "[KO vs EN 홍보 문구 비교 리포트]",
        "",
        "정직 고지: 두 언어 트랙은 서로 다른 페르소나 표본(KR/US)과 서로 다른 언어의 문구를 "
        "완전히 독립적으로 진화시킨 결과이며, 시뮬레이션 클릭 의향 비교이지 실측 A/B 테스트가 아닙니다.",
        "",
        "[우승 문구 나란히 비교]", "",
        "| | KO | EN |", "|---|---|---|",
    ]

    def _cell(final, field):
        w = final.get("winning_variant")
        if not w:
            return "(우승 없음)"
        if field == "score":
            return str(final.get("winning_score"))
        return str(w.get(field, ""))

    for field, label in (("headline", "headline"), ("body", "body"), ("cta", "cta"),
                          ("hook_type", "hook_type"), ("score", "score")):
        lines.append(f"| {label} | {_cell(ko_final, field)} | {_cell(en_final, field)} |")

    lines += ["", "[언어별 상위 hook_phrase]", "", "KO", ""]
    for p, c in ko_final.get("top_hook_phrases_overall", []) or [("(없음)", 0)]:
        lines.append(f"- '{p}' ({c})")
    lines += ["", "EN", ""]
    for p, c in en_final.get("top_hook_phrases_overall", []) or [("(none)", 0)]:
        lines.append(f"- '{p}' ({c})")

    lines += ["", "[언어별 상위 blocker]", "", "KO", ""]
    for b, c in ko_final.get("top_blockers_overall", []) or [("(없음)", 0)]:
        lines.append(f"- {b} ({c})")
    lines += ["", "EN", ""]
    for b, c in en_final.get("top_blockers_overall", []) or [("(none)", 0)]:
        lines.append(f"- {b} ({c})")

    ko_types = {v.get("hook_type") for v in ko_final.get("final_elites", [])} - {None}
    en_types = {v.get("hook_type") for v in en_final.get("final_elites", [])} - {None}
    common = sorted(ko_types & en_types)
    only_ko = sorted(ko_types - en_types)
    only_en = sorted(en_types - ko_types)
    lines += [
        "", "[최종 엘리트 기준 훅 유형 비교]", "",
        f"- 두 언어 모두에서 최종 엘리트에 든 훅 유형(공통으로 통함): {common or '(없음)'}",
        f"- KO에서만 최종 엘리트에 든 훅 유형: {only_ko or '(없음)'}",
        f"- EN에서만 최종 엘리트에 든 훅 유형: {only_en or '(없음)'}",
        "",
        f"- KO 총 호출/비용: {ko_final['total_calls_this_lang']} / ${ko_final['total_cost_usd_this_lang']:.4f}",
        f"- EN 총 호출/비용: {en_final['total_calls_this_lang']} / ${en_final['total_cost_usd_this_lang']:.4f}",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Cost projection (printed BEFORE the first paid call; hard-aborts if over)
# --------------------------------------------------------------------------

def load_seeds_list(lang: str) -> list:
    """시드 변이 배열을 읽는 단일 진입점. 개수는 항상 여기서 나온다."""
    obj = load_json(_seeds_path(lang))
    return obj["variants"] if isinstance(obj, dict) and "variants" in obj else obj


def print_cost_projection_and_check(langs: list[str], generations: int, max_budget_usd: float,
                                     dry_run: bool, resume_from: Path | None = None) -> None:
    # 세대당 콜 수는 실제 시드 파일을 세어서 구한다. 하드코딩된 18/9 를 쓰던 시절에는
    # 시드를 8개로 줄인 뒤에도 리포트가 18개라고 말했다(2026-09-01 적발).
    # 이어받기면 첫 세대 개체군은 시드 8개가 아니라 물려받은 엘리트(보통 3)다. 시드
    # 개수로 투사하면 상한을 과대 추정해, 실제로는 예산 안에 드는 실행이 사전 중단된다.
    if resume_from:
        per_lang = {}
        for lg in langs:
            n_first, _, _ = load_resume_population(resume_from, lg)
            # 세대 1 이후로는 엘리트 3 + 자식 5 = 8 로 복원된다.
            per_lang[lg] = len(n_first) + max(0, generations - 1) * 8
        calls_per_gen = {lg: n + generations * PROJECTION_MUTATION_CALLS_PER_GEN
                         for lg, n in per_lang.items()}
        projected_calls = sum(calls_per_gen.values())
        projected = projected_calls * ASSUMED_COST_PER_CALL_USD
        log("")
        log("=" * 70)
        log("[비용 사전투사] 이어받기 실행, 첫 유료 호출 전 상한 추정:")
        for lg in langs:
            log(f"    {lg}: 총 {per_lang[lg]}개 평가 + 돌연변이 {generations} = {calls_per_gen[lg]}콜")
        log(f"  투사 호출 수(상한) = {projected_calls}")
        log(f"  투사 비용(상한)   = ${projected:.2f}  (콜당 ${ASSUMED_COST_PER_CALL_USD})")
        log(f"  --max-budget-usd   = ${max_budget_usd:.2f}")
        log("=" * 70)
        if not dry_run and projected > max_budget_usd:
            raise EvolveError(
                f"투사 비용 ${projected:.2f} 가 --max-budget-usd ${max_budget_usd:.2f} 를 넘습니다. "
                f"유료 호출을 시작하지 않았습니다.")
        return
    per_lang = {lg: len(load_seeds_list(lg)) for lg in langs}
    calls_per_gen = {lg: n + PROJECTION_MUTATION_CALLS_PER_GEN for lg, n in per_lang.items()}
    projected_calls = sum(calls_per_gen.values()) * generations
    projected = projected_calls * ASSUMED_COST_PER_CALL_USD
    log("")
    log("=" * 70)
    log("[비용 사전투사] 첫 유료 호출 전 상한 추정:")
    log(f"  언어={langs} 세대={generations}")
    for lg in langs:
        log(f"    {lg}: 시드 {per_lang[lg]}개 + 돌연변이 1 = 세대당 {calls_per_gen[lg]}콜")
    log(f"  투사 호출 수(상한) = {projected_calls}")
    log(f"  투사 비용(상한)   = ${projected:.2f}  (콜당 ${ASSUMED_COST_PER_CALL_USD})")
    log(f"  단가 근거          = {ASSUMED_COST_SOURCE}")
    log(f"  --max-budget-usd   = ${max_budget_usd:.2f}")
    log("  주: 세대 1 이후 개체군은 엘리트 3 + 자식 5 = 8 로 줄어들 수 있어 실지출은 보통 더 낮다.")
    log("=" * 70)

    # 하드 중단. 투사 상한이 예산을 넘으면 유료 호출을 한 건도 하지 않고 멈춘다.
    # (2026-09-01: 투사 함수를 다시 쓰다가 이 검사를 실수로 지웠고, 드라이런에서
    #  $15.93 투사가 $15.00 상한을 넘겼는데도 그냥 진행되는 것을 보고 되살렸다.)
    if not dry_run and projected > max_budget_usd:
        raise EvolveError(
            f"투사 비용 ${projected:.2f} 가 --max-budget-usd ${max_budget_usd:.2f} 를 넘습니다. "
            f"유료 호출을 시작하지 않았습니다. 예산을 올리거나 --generations/시드 수를 줄이십시오.")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=["ko", "en", "both"], default="both")
    ap.add_argument("--personas-ko", type=Path, default=DEFAULT_PERSONAS_KO)
    ap.add_argument("--personas-en", type=Path, default=DEFAULT_PERSONAS_EN)
    ap.add_argument("--personas", type=Path, default=None,
                     help="override the persona file for a single-language run "
                          "(--lang ko or --lang en only; ignored/invalid with --lang both)")
    ap.add_argument("--out-dir", type=Path, default=Path("results"),
                     help="base output dir; writes <out-dir>/<lang>/... and <out-dir>/COMPARISON.md")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-budget-usd", type=float, default=DEFAULT_MAX_BUDGET_USD,
                     help=f"cumulative hard cap across the WHOLE invocation (default ${DEFAULT_MAX_BUDGET_USD})")
    ap.add_argument("--per-call-budget-usd", type=float, default=DEFAULT_PER_CALL_BUDGET_USD,
                     help="passed through as each individual `claude --max-budget-usd` ceiling")
    ap.add_argument("--max-calls", type=int, default=DEFAULT_MAX_CALLS)
    ap.add_argument("--timeout-s", type=int, default=600)
    ap.add_argument("--repeats", type=int, default=1,
                    help="변이 하나를 몇 번 판정할지. 실측 재판정 편차가 최대 7.84점이라 "
                         "그보다 작은 개선은 잡음과 구별되지 않는다. 3 이상 권장, 비용은 배수.")
    ap.add_argument("--generations", type=int, default=DEFAULT_GENERATIONS)
    ap.add_argument("--resume-from", type=Path, default=None,
                    help="이전 실행 결과 디렉토리. 그 언어의 FINAL_REPORT.json 에 담긴 "
                         "최종 엘리트를 세대 0 개체군으로 삼아 이어 돌린다. 시드부터 "
                         "다시 시작하면 이미 끝난 세대를 유료로 재계산하게 된다.")
    ap.add_argument("--gen-offset", type=int, default=None,
                    help="세대 번호 시작값. 기본은 --resume-from 의 마지막 세대 + 1 이라 "
                         "리포트의 세대 번호가 이전 실행과 이어진다.")
    ap.add_argument("--patience", type=int, default=DEFAULT_PATIENCE)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--w-yes", type=float, default=DEFAULT_W_YES)
    ap.add_argument("--w-maybe", type=float, default=DEFAULT_W_MAYBE)
    ap.add_argument("--w-trust", type=float, default=DEFAULT_W_TRUST)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--research-max-age-days", type=float, default=7.0)
    ap.add_argument("--research-auto-limit", type=int, default=8,
                     help="--limit passed to the auto-triggered `hook_research.py youtube` run")
    ap.add_argument("--no-auto-research", dest="auto_research", action="store_false", default=True,
                     help="refuse instead of auto-running hook_research.py when research is missing/stale")
    return ap


def main() -> int:
    args = build_arg_parser().parse_args()
    langs = ["ko", "en"] if args.lang == "both" else [args.lang]
    if args.personas is not None and args.lang == "both":
        print("FATAL: --personas cannot be used with --lang both (ambiguous) — "
              "use --personas-ko/--personas-en or run one language at a time.", file=sys.stderr)
        return 1

    try:
        ensure_research_fresh(args.research_max_age_days, args.research_auto_limit, args.auto_research)
        for lang in langs:
            ensure_seeds_available(lang, args.auto_research)
        print_cost_projection_and_check(langs, args.generations, args.max_budget_usd, args.dry_run,
                                        getattr(args, "resume_from", None))
    except EvolveError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1

    products = load_json(PRODUCTS_JSON)
    rng = random.Random(args.seed)
    budget = BudgetTracker(args.max_budget_usd, args.max_calls)

    finals: dict[str, dict] = {}
    try:
        for lang in langs:
            personas_path = args.personas if (args.personas and len(langs) == 1) else (
                args.personas_ko if lang == "ko" else args.personas_en
            )
            if not personas_path.exists():
                raise EvolveError(f"persona file not found for lang={lang}: {personas_path}")
            out_root = args.out_dir / lang
            finals[lang] = run_language(lang, args, personas_path, out_root, rng, budget, products)
    except (EvolveError, run_copy_harness.HarnessError) as e:
        print(f"FATAL: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if "ko" in finals and "en" in finals:
        cmp_md = render_comparison_md(finals["ko"], finals["en"])
        (args.out_dir / "COMPARISON.md").write_text(cmp_md, encoding="utf-8")
        log(f"wrote {args.out_dir / 'COMPARISON.md'}")

    log(f"\nGRAND TOTAL: calls={budget.total_calls} cost=${budget.total_cost:.4f} "
        f"(cap was ${args.max_budget_usd:.2f}) dry_run={args.dry_run}")
    for lang, final in finals.items():
        print(f"\n===== {lang} FINAL_REPORT.md =====\n")
        print((args.out_dir / lang / "FINAL_REPORT.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
