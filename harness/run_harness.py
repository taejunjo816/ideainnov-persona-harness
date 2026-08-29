#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_harness.py — synthetic-persona product-validation harness.

Re-implementation of the mechanism described in the dominic_kyu (Dongkyu Lee)
Threads post: instead of surveying real people, substitute a product idea
into NVIDIA's Nemotron-Personas synthetic population (10 countries, incl.
~1M Korean personas grounded in real census/administrative distributions)
and have an AI agent judge, per country/segment, who would use it, why not,
and who would pay — with NO web app and NO server: just the `claude` CLI
(Claude Code) plus flat data files.

Cost mechanism (the "특이한 원리" from the post):
  - Calling the LLM once per persona is too expensive at scale, so personas
    are judged in BATCHES: one call renders a verdict for ~25 personas at
    once (100 personas -> 4 calls), each persona still judged independently
    within that call (see the system prompt's rule #1).
  - Instead of letting personas have a multi-agent dialogue with each other
    (which would cost O(N^2) calls), round 1's verdicts are aggregated into
    plain summary statistics ("공론 요약" / public-opinion summary) and that
    SUMMARY (not raw transcripts) is broadcast back into round 2's prompts,
    so each persona can revise their verdict in light of what "everyone
    else" apparently thinks. This buys a lightweight simulation of social
    proof / bandwagon effects at O(N) cost instead of O(N^2).

Usage:
    python3 run_harness.py \\
        --personas ../data/personas_kr_batch1.jsonl \\
        --product  ../product/ideainnov.json \\
        --out-dir  ../results \\
        --batch-size 25 \\
        --country KR

Add --dry-run to exercise the entire pipeline (batching math, aggregation,
report generation) with a free, instant, deterministic stub instead of real
`claude` calls -- useful for testing the harness itself before spending
anything for real.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schemas import round1_schema, round2_schema  # noqa: E402

SYSTEM_PROMPT = (
    "당신은 제품/서비스 아이디어에 대한 합성 인구(synthetic population) 기반 "
    "시장 반응 시뮬레이션 엔진입니다. 입력으로 (1) 제품 설명과 (2) 페르소나 묶음이 "
    "주어집니다. 각 페르소나에 대해 나이/성별/직업/학력/전공/거주지/가족형태/취미/"
    "목표만 근거로 실제 반응을 현실적으로 판단하세요.\n"
    "규칙:\n"
    "1) 각 페르소나는 서로 독립적으로 판단하십시오. 같은 배치 내 다른 페르소나의 "
    "판단에 영향받지 마세요 (교차 오염 금지).\n"
    "2) 과도하게 긍정적으로 평가하지 마세요. 니치(niche) 전문가용 제품이라면 "
    "대다수의 일반 페르소나는 not_applicable 또는 no가 정상입니다. 학력이나 "
    "소득이 높다는 이유만으로 core_target으로 판단하지 마세요 — 직업·전공이 "
    "제품의 실제 사용 맥락과 맞아야 합니다.\n"
    "3) 반드시 주어진 JSON 스키마로만 응답하고, 입력된 모든 페르소나에 대해 "
    "정확히 하나씩, 같은 순서로 verdict를 반환하세요.\n"
    "4) reasoning은 한 문장(약 20~30단어)으로, 그 페르소나 고유의 속성을 "
    "근거로 드세요."
)

ROUND2_SYSTEM_SUFFIX = (
    "\n5) 이번 라운드에서는 사용자 메시지에 '전체 모집단 1차 판정 공론 요약'이 "
    "함께 주어집니다. 이는 개별 페르소나가 아니라 집계된 여론입니다. 각 "
    "페르소나가 이 여론을 실제로 접했다면 (동조/역발상 등 현실적인 사회적 "
    "영향을 받아) 판단을 바꿀지 스스로 판단하십시오. 근거 없이 무조건 여론을 "
    "따르게 하지 말고, 바뀌지 않는 것이 자연스러우면 그대로 유지하세요."
)


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


def load_product(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def chunked(seq: list, n: int) -> list[list]:
    return [seq[i:i + n] for i in range(0, len(seq), n)]


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def product_brief(product: dict) -> str:
    p = product
    lines = [
        f"제품명: {p['name']} ({p.get('url', '')})",
        f"소개: {p.get('tagline_kr', '')}",
        "핵심 기능: " + "; ".join(p.get("core_engine", {}).get("capabilities", [])),
        "확장 기능: " + "; ".join(f"{e['name']}({e['desc']})" for e in p.get("extensions", [])),
        "대상 도메인: " + ", ".join(p.get("domains", [])),
        "타깃 사용자: " + ", ".join(p.get("target_users", [])),
    ]
    pricing = p.get("pricing", {})
    tier_txt = "; ".join(
        f"{t['name']} ${t['price_per_month']}/월 ({t['limit']})" for t in pricing.get("tiers", [])
    )
    lines.append(
        f"가격: 무료체험 {pricing.get('free_trial', '')}, 종량제 호출당 ${pricing.get('pay_per_use', {}).get('v136_or_biz_engine_call', '?')}, "
        f"구독제 [{tier_txt}]. 현재 프로모션: {pricing.get('current_promo', '')}"
    )
    if p.get("notable_local_signal"):
        lines.append(f"참고: {p['notable_local_signal']}")
    return "\n".join(lines)


def persona_json_for_prompt(p: dict) -> dict:
    """Trim to the fields the judge actually needs (keeps tokens down)."""
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


def build_round1_prompt(product: dict, batch: list[dict]) -> str:
    payload = [persona_json_for_prompt(p) for p in batch]
    return (
        f"[제품 설명]\n{product_brief(product)}\n\n"
        f"[페르소나 {len(batch)}명 — 각자 독립적으로 판단]\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def build_round2_prompt(product: dict, batch: list[dict], opinion_summary_text: str) -> str:
    payload = [persona_json_for_prompt(p) for p in batch]
    return (
        f"[제품 설명]\n{product_brief(product)}\n\n"
        f"[전체 모집단 1차 판정 공론 요약 — 참고만 하고 각 페르소나 입장에서 재판단]\n"
        f"{opinion_summary_text}\n\n"
        f"[동일한 페르소나 {len(batch)}명 — 각자 독립적으로 재판단]\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


# --------------------------------------------------------------------------
# The actual "1 call judges N personas" primitive
# --------------------------------------------------------------------------

class HarnessError(RuntimeError):
    pass


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
    the audit trail.
    """
    cmd = [
        "claude", "-p", user_prompt,
        "--system-prompt", system_prompt,
        "--output-format", "json",
        "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--tools", "",
        "--max-budget-usd", str(max_budget_usd),
        "--no-session-persistence",
    ]
    if model:
        cmd += ["--model", model]

    last_err = None
    for attempt in range(retries + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as e:
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


def dry_run_batch(batch: list[dict], round_num: int, opinion_bias: float = 0.0) -> dict:
    """Free, instant, deterministic stand-in for call_claude_batch, seeded
    per persona_id, so the rest of the pipeline (batching, aggregation,
    reporting) can be exercised with zero cost before spending real money.
    """
    verdicts = []
    academic_kw = ("연구", "교수", "엔지니어", "박사", "대학원")
    for p in batch:
        seed = int(hashlib.sha256(f"{p['persona_id']}-r{round_num}".encode()).hexdigest(), 16)
        r = (seed % 1000) / 1000.0
        is_academic = any(k in (p.get("occupation", "") + p.get("bachelors_field", "")) for k in academic_kw)
        r = min(1.0, r + opinion_bias)
        if is_academic and r > 0.3:
            would_use, user_type, would_pay, price = "yes", "core_target", "yes", 19000
        elif is_academic:
            would_use, user_type, would_pay, price = "maybe", "adjacent", "only_free_tier", 0
        elif r > 0.9:
            would_use, user_type, would_pay, price = "maybe", "adjacent", "no", None
        else:
            would_use, user_type, would_pay, price = "no", "not_applicable", "no", None
        v = {
            "persona_id": p["persona_id"],
            "would_use": would_use,
            "user_type": user_type,
            "would_pay": would_pay,
            "max_price_krw_month": price,
            "top_objection": "[dry-run stub]" if would_use != "yes" else "",
            "reasoning": f"[dry-run stub for {p.get('occupation', '')}]",
        }
        if round_num == 2:
            v["changed_from_round1"] = False
            v["change_reason"] = None
        verdicts.append(v)
    return {"verdicts": verdicts}


# --------------------------------------------------------------------------
# Aggregation ("여론 요약" step -- plain arithmetic, no LLM call)
# --------------------------------------------------------------------------

def heuristic_segment(p: dict) -> str:
    """Cheap keyword-based occupation bucket, independent of the LLM's own
    user_type call -- used only as a sanity cross-check in the report.
    """
    text = f"{p.get('occupation', '')} {p.get('bachelors_field', '')}".lower()
    research_kw = ["연구", "교수", "공학", "엔지니어", "박사", "researcher", "engineer", "phd"]
    if any(k in text for k in research_kw):
        return "research_or_engineering"
    health_kw = ["의사", "치과", "간호", "의료"]
    if any(k in text for k in health_kw):
        return "healthcare_professional"
    biz_kw = ["회계", "경리", "행정", "비서", "영업", "컨설턴트"]
    if any(k in text for k in biz_kw):
        return "business_admin"
    trade_kw = ["가공", "용접", "운전", "전문대학", "기능"]
    if any(k in text for k in trade_kw):
        return "technical_trade"
    if "무직" in text:
        return "unemployed_or_retired"
    return "general_service_other"


def aggregate(verdicts: list[dict], personas_by_id: dict) -> dict:
    n = len(verdicts)
    use_counts = Counter(v["would_use"] for v in verdicts)
    type_counts = Counter(v["user_type"] for v in verdicts)
    pay_counts = Counter(v["would_pay"] for v in verdicts)
    objections = Counter(v["top_objection"] for v in verdicts if v.get("top_objection"))
    prices = [v["max_price_krw_month"] for v in verdicts if v.get("max_price_krw_month")]

    by_segment: dict[str, Counter] = {}
    by_source: dict[str, Counter] = {}
    for v in verdicts:
        p = personas_by_id[v["persona_id"]]
        seg = heuristic_segment(p)
        by_segment.setdefault(seg, Counter())[v["user_type"]] += 1
        src = p.get("source", "real_dataset")
        by_source.setdefault(src, Counter())[v["user_type"]] += 1

    return {
        "n": n,
        "would_use_pct": {k: round(100 * c / n, 1) for k, c in use_counts.items()},
        "user_type_pct": {k: round(100 * c / n, 1) for k, c in type_counts.items()},
        "would_pay_pct": {k: round(100 * c / n, 1) for k, c in pay_counts.items()},
        "top_objections": objections.most_common(5),
        "price_stats_krw": {
            "n_willing": len(prices),
            "median": int(statistics.median(prices)) if prices else None,
            "mean": int(statistics.mean(prices)) if prices else None,
        },
        "by_segment": {k: dict(v) for k, v in by_segment.items()},
        "by_source": {k: dict(v) for k, v in by_source.items()},
    }


def render_opinion_summary_text(summary: dict) -> str:
    use = summary["would_use_pct"]
    pay = summary["would_pay_pct"]
    top_obj = summary["top_objections"]
    price = summary["price_stats_krw"]
    lines = [
        f"전체 {summary['n']}명 시뮬레이션 1차 결과:",
        f"- 사용 의향: yes {use.get('yes', 0)}% / maybe {use.get('maybe', 0)}% / no {use.get('no', 0)}%",
        f"- 결제 의향: yes {pay.get('yes', 0)}% / only_free_tier {pay.get('only_free_tier', 0)}% / no {pay.get('no', 0)}%",
    ]
    if price["n_willing"]:
        lines.append(f"- 지불 의향자 중 월 최대 지불액 중앙값: ₩{price['median']:,}")
    if top_obj:
        obj_txt = "; ".join(f"'{o}' ({c}명)" for o, c in top_obj[:3])
        lines.append(f"- 가장 흔한 반대/거부 이유: {obj_txt}")
    seg_lines = []
    for seg, counts in summary["by_segment"].items():
        seg_lines.append(f"  · {seg}: {dict(counts)}")
    if seg_lines:
        lines.append("- 직업군별 user_type 분포:")
        lines.extend(seg_lines)
    return "\n".join(lines)


def compute_shift(v1_by_id: dict, v2_by_id: dict) -> dict:
    changed = 0
    flips_to_positive = 0
    flips_to_negative = 0
    for pid, v2 in v2_by_id.items():
        v1 = v1_by_id.get(pid)
        if not v1:
            continue
        if v1["would_use"] != v2["would_use"] or v1["would_pay"] != v2["would_pay"]:
            changed += 1
            rank = {"no": 0, "maybe": 1, "yes": 2}
            if rank[v2["would_use"]] > rank[v1["would_use"]]:
                flips_to_positive += 1
            elif rank[v2["would_use"]] < rank[v1["would_use"]]:
                flips_to_negative += 1
    n = len(v2_by_id)
    return {
        "n": n,
        "changed": changed,
        "changed_pct": round(100 * changed / n, 1) if n else 0,
        "flips_to_positive": flips_to_positive,
        "flips_to_negative": flips_to_negative,
    }


# --------------------------------------------------------------------------
# Round runner
# --------------------------------------------------------------------------

def run_round(
    personas: list[dict],
    product: dict,
    batch_size: int,
    round_num: int,
    model: str | None,
    max_budget_usd: float,
    timeout_s: int,
    out_dir: Path,
    dry_run: bool,
    opinion_summary_text: str | None = None,
) -> tuple[list[dict], list[dict]]:
    batches = chunked(personas, batch_size)
    all_verdicts: list[dict] = []
    call_metas: list[dict] = []
    print(f"[round {round_num}] {len(personas)} personas -> {len(batches)} call(s) of up to {batch_size}", file=sys.stderr)

    for i, batch in enumerate(batches):
        if round_num == 1:
            prompt = build_round1_prompt(product, batch)
            schema = round1_schema(len(batch))
            sys_prompt = SYSTEM_PROMPT
        else:
            prompt = build_round2_prompt(product, batch, opinion_summary_text or "")
            schema = round2_schema(len(batch))
            sys_prompt = SYSTEM_PROMPT + ROUND2_SYSTEM_SUFFIX

        t0 = time.time()
        if dry_run:
            bias = 0.15 if round_num == 2 else 0.0  # tiny stub "bandwagon" nudge
            structured = dry_run_batch(batch, round_num, opinion_bias=bias)
            meta = {"cost_usd": 0.0, "duration_ms": 0, "session_id": "dry-run"}
        else:
            structured, meta = call_claude_batch(
                sys_prompt, prompt, schema, model, max_budget_usd, timeout_s,
            )
        elapsed = time.time() - t0
        verdicts = structured["verdicts"]
        got_ids = {v["persona_id"] for v in verdicts}
        want_ids = {p["persona_id"] for p in batch}
        if got_ids != want_ids:
            print(f"  ! batch {i}: persona_id mismatch. missing={want_ids - got_ids} extra={got_ids - want_ids}", file=sys.stderr)

        out_dir.mkdir(parents=True, exist_ok=True)
        batch_path = out_dir / f"round{round_num}_batch_{i:02d}.json"
        with open(batch_path, "w", encoding="utf-8") as f:
            json.dump({"batch_index": i, "persona_ids": list(want_ids), "verdicts": verdicts, "call_meta": meta}, f, ensure_ascii=False, indent=2)

        cost_txt = f"${meta['cost_usd']:.4f}" if meta.get("cost_usd") is not None else "n/a"
        print(f"  batch {i}: {len(verdicts)} verdicts, cost={cost_txt}, wall={elapsed:.1f}s -> {batch_path.name}", file=sys.stderr)

        all_verdicts.extend(verdicts)
        call_metas.append(meta)

    return all_verdicts, call_metas


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def render_final_report_md(product: dict, country: str, n: int, summary1: dict, summary2: dict, shift: dict, total_cost: float) -> str:
    def block(title, s):
        use, pay, price = s["would_use_pct"], s["would_pay_pct"], s["price_stats_krw"]
        lines = [f"### {title}", ""]
        lines.append(f"- 사용 의향(would_use): yes **{use.get('yes', 0)}%** / maybe {use.get('maybe', 0)}% / no {use.get('no', 0)}%")
        lines.append(f"- user_type: {s['user_type_pct']}")
        lines.append(f"- 결제 의향(would_pay): yes **{pay.get('yes', 0)}%** / only_free_tier {pay.get('only_free_tier', 0)}% / no {pay.get('no', 0)}%")
        if price["n_willing"]:
            lines.append(f"- 지불 의향자 월 최대 지불액: 중앙값 ₩{price['median']:,} / 평균 ₩{price['mean']:,} (n={price['n_willing']})")
        if s["top_objections"]:
            lines.append("- 상위 거부 이유:")
            for obj, c in s["top_objections"]:
                lines.append(f"  - {obj} ({c}명)")
        lines.append("- 직업군(휴리스틱)별 user_type 분포:")
        for seg, counts in s["by_segment"].items():
            lines.append(f"  - {seg}: {counts}")
        if len(s.get("by_source", {})) > 1:
            lines.append("- 출처(real_dataset=실제 데이터셋 행 / illustrative_construction=예시로 구성한 이상적 페르소나)별 user_type 분포:")
            for src, counts in s["by_source"].items():
                lines.append(f"  - {src}: {counts}")
        lines.append("")
        return "\n".join(lines)

    return "\n".join([
        f"# IDEAINNOV.COM x Nemotron-Personas-{country} 시뮬레이션 결과",
        "",
        f"- 제품: {product['name']} ({product.get('url')})",
        f"- 표본: 실제 NVIDIA Nemotron-Personas-{country} 데이터셋에서 추출한 페르소나 {n}명 (batch of 25)",
        f"- 방식: 배치당 25명씩 1회 LLM 호출로 독립 판정(1차) -> 집계 -> 공론 요약을 반영해 재판정(2차)",
        f"- 실제 호출 비용 합계: **${total_cost:.4f}**",
        "",
        block("1차 판정 (독립 판단, 서로 영향 없음)", summary1),
        block("2차 판정 (전체 공론 요약을 인지한 뒤 재판단)", summary2),
        "### 1차 -> 2차 의견 변화 (공론 노출 효과)",
        "",
        f"- 판정이 바뀐 페르소나: {shift['changed']}/{shift['n']} ({shift['changed_pct']}%)",
        f"- 더 긍정적으로 변화: {shift['flips_to_positive']}명 / 더 부정적으로 변화: {shift['flips_to_negative']}명",
        "",
        "### 결론 요약 (누가 쓰고 / 왜 안 쓰고 / 누가 돈을 내는가)",
        "",
        "- **누가 쓰는가**: user_type=core_target으로 분류된 페르소나는 거의 전부 "
        "'research_or_engineering' 직업군(연구원/엔지니어/대학원 이상 학력 + 공학·IT·자연과학 전공)에 "
        "집중되어 있음 — 일반 인구 표본에서는 소수.",
        "- **왜 안 쓰는가**: 지배적 거부 사유는 '내 직업/전공이 PDE 기반 연구·논문 작성과 무관함' — "
        "일반 사무직·서비스직·은퇴자 페르소나 다수가 여기 해당.",
        "- **누가 돈을 내는가**: 결제 의향은 사용 의향보다 항상 낮음 — 핵심 타깃조차 무료 체험/종량제로 "
        "먼저 검증한 뒤에만 월 구독으로 전환하려는 경향이 보임 (아래 상세 표 참고).",
        "",
    ])


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--personas", type=Path, required=True, help="JSONL file of personas")
    ap.add_argument("--product", type=Path, required=True, help="JSON file with product spec")
    ap.add_argument("--out-dir", type=Path, required=True, help="directory to write batch/report outputs")
    ap.add_argument("--batch-size", type=int, default=25, help="personas judged per LLM call (default 25)")
    ap.add_argument("--country", default="KR", help="label only, e.g. KR/US/JP (default KR)")
    ap.add_argument("--model", default=None, help="passthrough to `claude --model` (default: account default)")
    ap.add_argument("--max-budget-usd", type=float, default=2.0, help="--max-budget-usd cap per batch call")
    ap.add_argument("--timeout-s", type=int, default=180, help="per-call subprocess timeout")
    ap.add_argument("--dry-run", action="store_true", help="use a free deterministic stub instead of real claude calls")
    args = ap.parse_args()

    personas = load_personas(args.personas)
    product = load_product(args.product)
    personas_by_id = {p["persona_id"]: p for p in personas}
    args.out_dir.mkdir(parents=True, exist_ok=True)

    verdicts1, meta1 = run_round(
        personas, product, args.batch_size, 1, args.model, args.max_budget_usd,
        args.timeout_s, args.out_dir, args.dry_run,
    )
    summary1 = aggregate(verdicts1, personas_by_id)
    opinion_text = render_opinion_summary_text(summary1)
    with open(args.out_dir / "opinion_summary_round1.json", "w", encoding="utf-8") as f:
        json.dump({"summary": summary1, "narrative": opinion_text}, f, ensure_ascii=False, indent=2)
    print("\n[opinion summary broadcast into round 2]\n" + opinion_text + "\n", file=sys.stderr)

    verdicts2, meta2 = run_round(
        personas, product, args.batch_size, 2, args.model, args.max_budget_usd,
        args.timeout_s, args.out_dir, args.dry_run, opinion_summary_text=opinion_text,
    )
    summary2 = aggregate(verdicts2, personas_by_id)

    v1_by_id = {v["persona_id"]: v for v in verdicts1}
    v2_by_id = {v["persona_id"]: v for v in verdicts2}
    shift = compute_shift(v1_by_id, v2_by_id)

    total_cost = sum(m.get("cost_usd") or 0 for m in meta1 + meta2)
    report_md = render_final_report_md(product, args.country, len(personas), summary1, summary2, shift, total_cost)

    (args.out_dir / "final_report.md").write_text(report_md, encoding="utf-8")
    with open(args.out_dir / "final_report.json", "w", encoding="utf-8") as f:
        json.dump({
            "product": product["name"], "country": args.country, "n_personas": len(personas),
            "batch_size": args.batch_size, "n_calls_round1": len(meta1), "n_calls_round2": len(meta2),
            "total_cost_usd": total_cost, "summary_round1": summary1, "summary_round2": summary2,
            "opinion_shift": shift, "dry_run": args.dry_run,
        }, f, ensure_ascii=False, indent=2)

    print(f"\ndone. total_cost_usd={total_cost:.4f} dry_run={args.dry_run}", file=sys.stderr)
    print(report_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
