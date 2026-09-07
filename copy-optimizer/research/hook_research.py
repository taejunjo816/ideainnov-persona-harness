#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hook_research.py — real, public, free-tier "what hooks are working right
now" research feeding `copy/seed_variants.json`.

Three subcommands:

  youtube     Pull real YouTube search metadata (title/tags/description/
              view_count/upload_date/...) via `yt-dlp`, no API key, no
              download. Classify titles into hook types (rule-based, with
              an optional --use-llm assist for ambiguous ones), analyze
              tags and description structure, weight everything by
              views/day. Writes research/out/youtube_hooks.json +
              research/out/HOOK_REPORT.md.

  instagram   Honest [SKIP]: there is no public API for "what's popular on
              Instagram right now" for accounts you don't own, and scraping
              violates ToS, so this does not pretend to fetch anything.
              Instead it ingests any CSV you drop in research/inbox/ (a
              'title' or 'caption' column) — e.g. content you exported by
              hand from Meta Business Suite / Instagram's own "Download
              Your Information" tool — and classifies it the same way.

  seeds       Build copy/seed_variants.json (18 entries). THIS PROGRAM'S
              seeds are built FROM the youtube research: the mix of hook
              types across the 18 seeds mirrors the observed
              views/day-weighted hook-type distribution in
              research/out/youtube_hooks.json. Research decides the FORM
              (which structural hook pattern each seed uses); a curated,
              evidence-cited content pool (grounded only in
              common/products.json) decides the CONTENT. Never copies a
              real title/tag/description verbatim.

Nothing here ever calls the paid `claude` CLI unless you explicitly pass
--use-llm (youtube subcommand only, for ambiguous-title classification).
Everything else is free (yt-dlp search + local rule-based classification).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # 홍보문구최적화/
OUT_DIR = HERE / "out"
INBOX_DIR = HERE / "inbox"
PRODUCTS_JSON = PROJECT_ROOT.parent / "common" / "products.json"
# seed_variants_<lang>.json paths are built by _seeds_path_for_lang() below.

HOOK_TYPES = [
    "질문형", "숫자형", "역설·반전", "부정형",
    "정체성호명", "시간압박", "호기심갭", "결과선공개",
]

TEMPLATE_TEXT = {
    "질문형": "정체성/상황 호명 + 물음표로 끝나는 질문",
    "숫자형": "숫자 + 단위 + 결과/효과",
    "역설·반전": "통념 제시 + '그런데/사실은' 반전 + 실제 사실",
    "부정형": "부정 명령('~하지 마세요') + 이유",
    "정체성호명": "특정 독자 직접 호명 + 그 독자에게 맞춘 약속",
    "시간압박": "마감/기한 표현 + 즉시 행동 촉구",
    "호기심갭": "결과를 암시만 하고 이유는 감추는 열린 문장",
    "결과선공개": "과정/순서를 그대로 여러 단계로 나열",
}


class ResearchError(RuntimeError):
    pass


# ==========================================================================
# 0. small utils
# ==========================================================================

def slugify(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", text.strip()).strip("_")
    return s[:60] or "query"


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def days_since(upload_date: str | None, today: date) -> int | None:
    if not upload_date or not re.fullmatch(r"\d{8}", str(upload_date)):
        return None
    try:
        d = datetime.strptime(str(upload_date), "%Y%m%d").date()
    except ValueError:
        return None
    return max((today - d).days, 1)


# ==========================================================================
# 1. rule-based classifiers
# ==========================================================================

_NEG_KW = ["하지 마", "하지마", "말아야", "금지", "절대 ", "don't", "never", "no more"]
_DEADLINE_KW = ["마감", "오늘", "지금", "한정", "곧", "임박", "이번주", "이번 주",
                "올해 안", "d-", "deadline", "last chance", "hurry", "지금 바로"]
_IDENTITY_KW = ["대학원생", "연구원", "교수", "박사", "석사", "당신", "너라면",
                "여러분", "researchers", "grad student", "graduate student", "phd", "scientist"]
_PARADOX_KW = ["그런데", "사실은", "반전", "몰랐던", "충격", "아니었다", "뒤집힌",
               "반대로", "turns out", "actually", "surprisingly", "alert"]
_CURIOSITY_KW = ["이유", "비밀", "방법", "노하우", "꿀팁", "이렇게 하면", "비법",
                 "왜", "secret", "reason why", "hack"]
_RESULT_FIRST_KW = ["전후", "비교", "완성", "총정리", "총 정리", "한번에 정리",
                    "step by step", "step-by-step", "완성했습니다", "결과", "후기"]


def classify_hook_type(title: str) -> tuple[str, str]:
    """Rule-based, priority-ordered. Returns (hook_type_or_'기타', matched_rule)."""
    t = title.lower()
    if "?" in title or "？" in title:
        return "질문형", "물음표 포함"
    if any(k in t for k in _NEG_KW):
        return "부정형", "부정 명령/금지 표현"
    if any(k in t for k in _DEADLINE_KW):
        return "시간압박", "마감/기한 표현"
    if any(k in t for k in _IDENTITY_KW):
        return "정체성호명", "특정 독자 호칭"
    if any(k in t for k in _PARADOX_KW):
        return "역설·반전", "반전 접속사/표현"
    if re.search(r"\d", title) and re.search(r"\d\s*(개|분|일|%|배|만원|시간|위|가지)", title):
        return "숫자형", "숫자+단위"
    if any(k in t for k in _CURIOSITY_KW):
        return "호기심갭", "결과 암시/이유 은닉 표현"
    if any(k in t for k in _RESULT_FIRST_KW):
        return "결과선공개", "결과/과정 선공개 표현"
    if re.search(r"\d", title):
        return "숫자형", "숫자 포함(단위 불명확)"
    return "기타", "규칙 매칭 없음"


def classify_desc_line(line: str) -> str:
    s = line.strip()
    if not s:
        return "빈줄"
    if re.search(r"https?://", s):
        return "링크"
    if re.search(r"\b\d{1,2}:\d{2}(:\d{2})?\b", s):
        return "타임스탬프"
    if re.fullmatch(r"(#\S+\s*)+", s):
        return "해시태그"
    if any(k in s for k in ["구독", "좋아요", "팔로우", "알림설정", "subscribe", "follow", "like and"]):
        return "CTA"
    if len(s) > 40:
        return "요약/설명"
    return "제목반복/기타"


_BRAND_SUFFIX_KW = ["아카데미", "academy", "tv", "채널", "official", "랩", "lab",
                     "센터", "center", "교수", "professor", "스튜디오", "studio"]


def classify_tag_category(tag: str, channel_counts: Counter) -> str:
    if channel_counts.get(tag, 0) >= 2:
        return "주제태그"
    low = tag.lower()
    if any(k in low for k in _BRAND_SUFFIX_KW):
        return "브랜드태그"
    return "롱테일태그"


# ==========================================================================
# 2. yt-dlp wrapper (per-video --dump-json, NOT --flat-playlist — flat mode
#    omits tags/description, which this analysis needs)
# ==========================================================================

def fetch_query_raw(query: str, limit: int, timeout_s: int, refresh: bool, log) -> list[dict]:
    """Returns raw yt-dlp JSON records for one query, using a per-query cache
    file (research/out/raw_<slug>.json) so re-runs (e.g. `seeds` after
    `youtube`, or a second verify pass) don't refetch from YouTube."""
    slug = slugify(query)
    cache_path = OUT_DIR / f"raw_{slug}.json"
    if cache_path.exists() and not refresh:
        cached = load_json(cache_path)
        if len(cached) >= limit:
            log(f"  [cache] {query!r}: reusing {cache_path.name} ({len(cached)} cached, need {limit})")
            return cached[:limit]
        log(f"  [cache] {query!r}: cache has {len(cached)} < requested {limit}, refetching")

    cmd = ["yt-dlp", f"ytsearch{limit}:{query}", "--dump-json", "--skip-download", "--no-warnings"]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, encoding="utf-8")
    except FileNotFoundError:
        raise ResearchError("yt-dlp is not installed / not on PATH. Install it or run with inbox-only "
                             "data via the `instagram` subcommand's CSV ingest.")
    except subprocess.TimeoutExpired:
        raise ResearchError(f"yt-dlp timed out after {timeout_s}s on query {query!r} (limit={limit}); "
                             f"lower --limit or raise --timeout-s.")
    elapsed = time.time() - t0
    if proc.returncode != 0 and not proc.stdout.strip():
        raise ResearchError(f"yt-dlp failed for query {query!r}: exit={proc.returncode} "
                             f"stderr={proc.stderr[:400]!r}")

    records = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            log(f"  ! skipping non-JSON yt-dlp output line ({len(line)} chars)")
    log(f"  [yt-dlp] {query!r}: {len(records)} results in {elapsed:.1f}s "
        f"({elapsed / max(len(records), 1):.2f}s/video)")
    dump_json(cache_path, records)
    return records


def normalize_record(raw: dict, query: str, today: date) -> dict:
    upload_date = raw.get("upload_date")
    view_count = raw.get("view_count") or 0
    dsince = days_since(upload_date, today)
    views_per_day = round(view_count / dsince, 2) if dsince else None
    return {
        "video_id": raw.get("id"),
        "title": raw.get("title") or "",
        "view_count": view_count,
        "like_count": raw.get("like_count"),
        "comment_count": raw.get("comment_count"),
        "upload_date": upload_date,
        "duration": raw.get("duration"),
        "channel": raw.get("channel") or raw.get("uploader") or "",
        "categories": raw.get("categories") or [],
        "tags": raw.get("tags") or [],
        "description": raw.get("description") or "",
        "url": raw.get("webpage_url") or raw.get("url") or "",
        "query": query,
        "views_per_day": views_per_day,
    }


# ==========================================================================
# 3. optional LLM assist for ambiguous ('기타') titles — off by default
# ==========================================================================

def classify_ambiguous_with_llm(titles: list[str], model: str | None, max_budget_usd: float,
                                 timeout_s: int, log) -> dict[str, str]:
    """Batches ambiguous titles into ONE `claude -p --json-schema` call.
    Guarded behind --use-llm; never called otherwise. Returns {title: hook_type}."""
    if not titles:
        return {}
    schema = {
        "type": "object",
        "properties": {
            "labels": {
                "type": "array", "minItems": len(titles), "maxItems": len(titles),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "hook_type": {"type": "string", "enum": HOOK_TYPES + ["기타"]},
                    },
                    "required": ["title", "hook_type"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["labels"],
        "additionalProperties": False,
    }
    sys_prompt = (
        "당신은 영상 제목의 '훅(hook) 유형'을 분류하는 엔진입니다. 아래 8개 유형 중 "
        "가장 가까운 하나로만 분류하세요: " + ", ".join(HOOK_TYPES) + ". "
        "애매하면 '기타'로 답하세요. 각 제목을 독립적으로 판단하고, 입력된 모든 제목에 "
        "대해 정확히 하나씩 같은 순서로 답하세요."
    )
    user_prompt = json.dumps({"titles": titles}, ensure_ascii=False)
    cmd = [
        "claude", "-p", user_prompt, "--system-prompt", sys_prompt,
        "--output-format", "json", "--json-schema", json.dumps(schema, ensure_ascii=False),
        "--tools", "", "--max-budget-usd", str(max_budget_usd), "--no-session-persistence",
    ]
    if model:
        cmd += ["--model", model]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0 and not proc.stdout.strip():
        raise ResearchError(f"--use-llm classification call failed: exit={proc.returncode} "
                             f"stderr={proc.stderr[:400]!r}")
    envelope = json.loads(proc.stdout)
    if envelope.get("is_error"):
        raise ResearchError(f"--use-llm classification call reported error: {envelope.get('result')}")
    structured = envelope.get("structured_output") or json.loads(envelope.get("result", "{}"))
    log(f"  [llm] classified {len(titles)} ambiguous titles, cost=${envelope.get('total_cost_usd', 0):.4f}")
    return {item["title"]: item["hook_type"] for item in structured.get("labels", [])}


# ==========================================================================
# 4. aggregation
# ==========================================================================

def aggregate_hook_types(records: list[dict]) -> list[dict]:
    weighted = defaultdict(float)
    counts = Counter()
    for r in records:
        weighted[r["hook_type"]] += (r["views_per_day"] or 0.0)
        counts[r["hook_type"]] += 1
    total_weighted = sum(weighted.values()) or 1.0
    total_count = sum(counts.values()) or 1
    rows = []
    for t in list(weighted.keys()):
        rows.append({
            "hook_type": t,
            "n_videos": counts[t],
            "weighted_views_per_day": round(weighted[t], 1),
            "share_pct_by_views": round(100 * weighted[t] / total_weighted, 1),
            "share_pct_by_count": round(100 * counts[t] / total_count, 1),
        })
    rows.sort(key=lambda r: r["weighted_views_per_day"], reverse=True)
    return rows


def aggregate_tags(records: list[dict], top_n: int = 20) -> list[dict]:
    tag_channel_presence: dict[str, set] = defaultdict(set)
    tag_weight = defaultdict(float)
    tag_count = Counter()
    for r in records:
        for tag in r.get("tags") or []:
            tag = tag.strip()
            if not tag:
                continue
            tag_channel_presence[tag].add(r["channel"])
            tag_weight[tag] += (r["views_per_day"] or 0.0)
            tag_count[tag] += 1
    cross_channel_counts = Counter({t: len(chs) for t, chs in tag_channel_presence.items()})
    rows = []
    for tag, w in tag_weight.items():
        rows.append({
            "tag": tag,
            "n_videos": tag_count[tag],
            "n_channels": len(tag_channel_presence[tag]),
            "weighted_views_per_day": round(w, 1),
            "category": classify_tag_category(tag, cross_channel_counts),
        })
    rows.sort(key=lambda r: r["weighted_views_per_day"], reverse=True)
    return rows[:top_n]


def aggregate_description_patterns(records: list[dict], top_n: int = 3) -> dict:
    combos = Counter()
    lengths = []
    hashtag_counts = []
    hashtag_positions = Counter()
    n_with_desc = 0
    for r in records:
        desc = (r.get("description") or "").strip()
        if not desc:
            continue
        n_with_desc += 1
        lengths.append(len(desc))
        lines = [ln for ln in desc.splitlines()]
        first3 = (lines + ["", "", ""])[:3]
        combo = tuple(classify_desc_line(ln) for ln in first3)
        combos[combo] += 1

        hashtags = re.findall(r"#\S+", desc)
        hashtag_counts.append(len(hashtags))
        if hashtags:
            first_idx = desc.find("#")
            ratio = first_idx / len(desc)
            bucket = "시작부" if ratio < 0.2 else ("끝부분" if ratio > 0.8 else "본문중간")
            hashtag_positions[bucket] += 1

    top_combos = combos.most_common(top_n)
    templates = []
    for combo, n in top_combos:
        steps = " → ".join(f"{i+1}줄: {t}" for i, t in enumerate(combo) if t != "빈줄")
        templates.append({"pattern": steps or "(설명 없음/1줄 미만)", "n_videos": n})

    return {
        "n_videos_with_description": n_with_desc,
        "avg_length_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "avg_hashtag_count": round(sum(hashtag_counts) / len(hashtag_counts), 2) if hashtag_counts else 0,
        "hashtag_position_mode": hashtag_positions.most_common(1)[0][0] if hashtag_positions else "해시태그 없음",
        "hashtag_position_counts": dict(hashtag_positions),
        "templates": templates,
    }


# ==========================================================================
# 5. report rendering
# ==========================================================================

def render_hook_report_md(meta: dict, hook_freq: list[dict], tag_top20: list[dict],
                           desc_patterns: dict, top10: list[dict],
                           hook_freq_by_lang: dict | None = None) -> str:
    lines = [
        "[홍보 훅 리서치 리포트 (YouTube 실측 공개 메타데이터)]",
        "",
        f"- 조회 시각: {meta['generated_at']}",
        f"- 쿼리: {', '.join(meta['queries'])}",
        f"- 쿼리당 조회 개수(--limit): {meta['limit']}",
        f"- 총 수집 영상: {meta['n_records']}개 (그중 업로드일 확인되어 views/day 계산 가능: {meta['n_with_views_per_day']}개)",
        "- 주의(정직 고지): 이 표는 유튜브 공개 검색 결과 메타데이터(제목/태그/설명/조회수/업로드일)에 대한 "
        "실측 관찰이며, ideainnov.com과 무관한 제3자 채널의 콘텐츠입니다. 'AI scientist' 쿼리는 과거 조사에서 "
        "data scientist 관련 콘텐츠로 결과가 오염되는 경향이 관측된 바 있어 그대로 유지하되 참고 바랍니다.",
        "",
        "[1) 제목 훅 유형표 (views/day 가중)]",
        "",
        "| 훅 유형 | 영상 수 | 가중 views/day 합계 | 비중(views/day 기준) | 비중(영상 수 기준) |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in hook_freq:
        lines.append(
            f"| {row['hook_type']} | {row['n_videos']} | {row['weighted_views_per_day']:,} | "
            f"{row['share_pct_by_views']}% | {row['share_pct_by_count']}% |"
        )
    lines += ["", "[2) 구조 템플릿 5개 (상위 훅 유형에서 도출 — 문구 아님, 구조만)]", ""]
    for row in hook_freq[:5]:
        t = row["hook_type"]
        lines.append(f"- {t} ({row['share_pct_by_views']}%): {TEMPLATE_TEXT.get(t, '(정의 없음)')}")
    lines += ["", "[3) 태그 상위 20 (weighted views/day 기준, 주제/브랜드/롱테일 구분)]", ""]
    lines += ["| 태그 | 분류 | 등장 영상 수 | 채널 수 | 가중 views/day |", "|---|---|---:|---:|---:|"]
    for row in tag_top20:
        lines.append(
            f"| {row['tag']} | {row['category']} | {row['n_videos']} | {row['n_channels']} | "
            f"{row['weighted_views_per_day']:,} |"
        )
    lines += ["", "[4) 설명문 구조 템플릿 3개]", "",
              f"- 설명문이 있는 영상: {desc_patterns['n_videos_with_description']}개",
              f"- 평균 길이: {desc_patterns['avg_length_chars']}자, 평균 해시태그 개수: {desc_patterns['avg_hashtag_count']}개, "
              f"해시태그 위치 최빈값: {desc_patterns['hashtag_position_mode']}", ""]
    for i, tpl in enumerate(desc_patterns["templates"], 1):
        lines.append(f"{i}. {tpl['pattern']}  (n={tpl['n_videos']})")
    lines += ["", "[5) views/day 상위 10 (참고용 원자료 — 세부 항목)]", "",
              "| 순위 | 훅 유형 | 채널 | views/day | 쿼리 |", "|---:|---|---|---:|---|"]
    for i, r in enumerate(top10, 1):
        lines.append(f"| {i} | {r['hook_type']} | {r['channel']} | {r['views_per_day']:,} | {r['query']} |")

    if hook_freq_by_lang:
        lines += ["", "[부록) 쿼리 언어별 훅 유형 비교 (KO 쿼리 vs EN 쿼리)]", "",
                   f"- KO 쿼리로 수집된 영상: {meta.get('n_records_by_lang', {}).get('ko', 0)}개 / "
                   f"EN 쿼리로 수집된 영상: {meta.get('n_records_by_lang', {}).get('en', 0)}개",
                   "- `copy/seed_variants_en.json`은 이 EN 쿼리 서브셋의 분포를 우선 사용하고, "
                   "표본이 얕으면(영상 5개 미만 또는 가중합 0) 위 1)번 전체(pooled) 분포로 대체하며 그 사실을 로그에 남깁니다.",
                   ""]
        for lang, label in (("ko", "KO 쿼리"), ("en", "EN 쿼리")):
            rows = hook_freq_by_lang.get(lang, [])
            lines.append(f"[{label}]")
            lines.append("")
            if not rows:
                lines.append("(이 언어 쿼리에서 분류 가능한 영상 없음)")
            else:
                lines += ["| 훅 유형 | 영상 수 | 가중 views/day | 비중 |", "|---|---:|---:|---:|"]
                for row in rows:
                    lines.append(f"| {row['hook_type']} | {row['n_videos']} | "
                                  f"{row['weighted_views_per_day']:,} | {row['share_pct_by_views']}% |")
            lines.append("")

    lines.append("")
    return "\n".join(lines)


# ==========================================================================
# 6. subcommand: youtube
# ==========================================================================

def cmd_youtube(args) -> int:
    def log(msg):
        print(msg, file=sys.stderr)

    queries_data = load_json(Path(args.queries))
    ko_queries = queries_data.get("ko", [])
    en_queries = queries_data.get("en", [])
    queries = list(dict.fromkeys(ko_queries + en_queries))  # de-dup, keep order (single fetch per unique string)
    # 'AI scientist' is listed in BOTH ko/en per spec; tag it 'en' (it's an English
    # phrase) so it counts toward the EN-track distribution, not double-fetched.
    query_lang_map = {q: "ko" for q in ko_queries}
    query_lang_map.update({q: "en" for q in en_queries})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today()

    all_records = []
    for q in queries:
        try:
            raw = fetch_query_raw(q, args.limit, args.timeout_s, args.refresh, log)
        except ResearchError as e:
            log(f"FATAL: {e}")
            return 1
        for r in raw:
            rec = normalize_record(r, q, today)
            rec["query_lang"] = query_lang_map.get(q, "ko")
            all_records.append(rec)

    # de-dup by video_id (a video can surface for multiple queries)
    seen = {}
    for r in all_records:
        seen.setdefault(r["video_id"], r)
    records = list(seen.values())

    for r in records:
        hook_type, rule = classify_hook_type(r["title"])
        r["hook_type"] = hook_type
        r["hook_type_rule"] = rule

    if args.use_llm:
        ambiguous_titles = list({r["title"] for r in records if r["hook_type"] == "기타"})
        if ambiguous_titles:
            log(f"[llm] {len(ambiguous_titles)} ambiguous titles -> --use-llm classification call")
            try:
                labels = classify_ambiguous_with_llm(
                    ambiguous_titles, args.model, args.max_budget_usd, args.timeout_s, log,
                )
            except ResearchError as e:
                log(f"FATAL: {e}")
                return 1
            for r in records:
                if r["title"] in labels:
                    r["hook_type"] = labels[r["title"]]
                    r["hook_type_rule"] = "llm-assisted"

    n_with_vpd = sum(1 for r in records if r["views_per_day"] is not None)
    hook_freq = aggregate_hook_types([r for r in records if r["hook_type"] != "기타"])
    hook_freq_by_lang = {
        lang: aggregate_hook_types([r for r in records if r["hook_type"] != "기타" and r["query_lang"] == lang])
        for lang in ("ko", "en")
    }
    tag_top20 = aggregate_tags([r for r in records if r["views_per_day"] is not None])
    desc_patterns = aggregate_description_patterns(records)
    top10 = sorted(
        [r for r in records if r["views_per_day"] is not None],
        key=lambda r: r["views_per_day"], reverse=True,
    )[:10]

    n_records_by_lang = Counter(r["query_lang"] for r in records)
    meta = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "queries": queries,
        "limit": args.limit,
        "n_records": len(records),
        "n_with_views_per_day": n_with_vpd,
        "n_records_by_lang": dict(n_records_by_lang),
        "use_llm": args.use_llm,
    }
    out_obj = {
        "meta": meta,
        "hook_type_freq": hook_freq,
        "hook_type_freq_by_lang": hook_freq_by_lang,
        "tag_top20": tag_top20,
        "description_patterns": desc_patterns,
        "top10_by_views_per_day": top10,
        "records": records,
    }
    dump_json(OUT_DIR / "youtube_hooks.json", out_obj)
    report_md = render_hook_report_md(meta, hook_freq, tag_top20, desc_patterns, top10, hook_freq_by_lang)
    (OUT_DIR / "HOOK_REPORT.md").write_text(report_md, encoding="utf-8")
    log(f"\nwrote {OUT_DIR / 'youtube_hooks.json'}")
    log(f"wrote {OUT_DIR / 'HOOK_REPORT.md'}")
    print(report_md)
    return 0


# ==========================================================================
# 7. subcommand: instagram (honest [SKIP] + manual CSV inbox)
# ==========================================================================

def cmd_instagram(args) -> int:
    print(
        "[SKIP] Instagram에는 '다른 계정의 인기 게시물'을 조회할 수 있는 공개 API가 없습니다.\n"
        "  - Graph API(Instagram Content Publishing/Insights)는 본인이 관리하는 비즈니스 계정에만 동작합니다.\n"
        "  - 공개 페이지 스크래핑은 Meta 이용약관(ToS) 위반이라 이 프로그램은 시도하지 않습니다.\n"
        "  - 대신 사람이 직접 내보낸 데이터를 받습니다: research/inbox/ 아래에 'title' 또는 'caption' 열이\n"
        "    있는 CSV를 넣으면 아래에서 그 파일을 읽어 유튜브 데이터와 같은 방식으로 훅 유형 분류를 합니다.\n"
        "  - 수동 내보내기 방법: Meta Business Suite > 콘텐츠 > 내보내기(CSV), 또는 Instagram 설정 >\n"
        "    '내 정보 다운로드'(JSON/CSV)에서 게시물 caption을 추출해 title/caption 열로 정리하세요.",
        file=sys.stderr,
    )
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    csv_files = sorted(INBOX_DIR.glob("*.csv"))
    if not csv_files:
        print(f"[SKIP] research/inbox/ 에 CSV가 없습니다 (0개 처리). 위 안내대로 파일을 넣고 다시 실행하세요.",
              file=sys.stderr)
        dump_json(OUT_DIR / "instagram_hooks.json", {
            "meta": {"generated_at": datetime.now().isoformat(timespec="seconds"), "n_rows": 0},
            "rows": [],
        })
        return 0

    rows = []
    for csv_path in csv_files:
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not ({"title", "caption"} & set(reader.fieldnames)):
                print(f"  ! {csv_path.name}: 'title' 또는 'caption' 열이 없어 건너뜁니다 "
                      f"(열: {reader.fieldnames})", file=sys.stderr)
                continue
            for row in reader:
                text = (row.get("title") or row.get("caption") or "").strip()
                if not text:
                    continue
                hook_type, rule = classify_hook_type(text)
                rows.append({
                    "source": f"manual:{csv_path.name}",
                    "text": text,
                    "hook_type": hook_type,
                    "hook_type_rule": rule,
                })
    print(f"[inbox] {len(csv_files)}개 CSV에서 {len(rows)}개 행 수집·분류", file=sys.stderr)
    dump_json(OUT_DIR / "instagram_hooks.json", {
        "meta": {"generated_at": datetime.now().isoformat(timespec="seconds"), "n_rows": len(rows),
                 "files": [p.name for p in csv_files]},
        "rows": rows,
    })
    return 0


# ==========================================================================
# 8. content pool for `seeds` — CONTENT is grounded in products.json,
#    FORM (which hook_type each item belongs to) is fixed at authoring time
#    so `seeds` can pick a data-driven MIX of these 24 items (3 per hook
#    type) proportional to the observed research distribution.
# ==========================================================================

def _e(path: str) -> str:
    return path  # evidence citation string, kept as a plain products.json path for the audit table


POOL: dict[str, list[dict]] = {
    "질문형": [
        {"suffix": "권위", "program": "paper",
         "headline": "가상 심사위원, 정말 3번이나 퇴짜를 놓을까요?",
         "body": "SCI Q1 11절 자동 심사 루프가 반려 사유까지 짚어주고, 그걸 반영해 초안을 다시 씁니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.features[3]"), _e("programs.paper.hooks_ko.thread[1]")]},
        {"suffix": "수식신뢰", "program": "paper",
         "headline": "수식 47개, 정말 안 깨질까요?",
         "body": "자연어 한 줄을 넣으면 편집 가능한 수식 47개가 담긴 논문 초안이 나옵니다. 직접 열어서 확인해 보세요.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.hooks_ko.short[0]"), _e("programs.paper.hooks_en.thread[0]")]},
        {"suffix": "저널탐색", "program": "sci",
         "headline": "투고할 저널, 아직도 하나씩 찾고 계신가요?",
         "body": "제목·초록·키워드만 넣으면 Q1 여부, SJR, 게재비, 심사기간까지 붙은 후보가 무료로 나옵니다.",
         "cta": "저널 매칭은 무료로 시작",
         "evidence": [_e("programs.sci.hooks_ko.thread[0]"), _e("programs.sci.price_ko")]},
    ],
    "숫자형": [
        {"suffix": "가격", "program": "paper",
         "headline": "₩4,100에 수식 47개, 심사 3회",
         "body": "종량제 ₩4,100/호출로 시작해 가상 심사위원에게 3회 퇴짜 맞으며 다듬은 뒤, "
                 "편집 가능한 수식 47개짜리 초안을 받습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.price_ko"), _e("programs.paper.hooks_ko.short[0]"),
                      _e("programs.paper.hooks_ko.thread[1]")]},
        {"suffix": "형식개수", "program": "hwp",
         "headline": "형식 변환 47개, 호출당 2,800원",
         "body": "HWPX·DOCX·PDF 등 47개 형식 상호 변환이 종량제 ₩2,800/호출로 시작됩니다.",
         "cta": "무료 체험 시작",
         "evidence": [_e("programs.hwp.features[0]"), _e("programs.hwp.price_ko")]},
        {"suffix": "용량한도", "program": "hwp",
         "headline": "20MB·30페이지, 넘으면 자동 분할",
         "body": "20MB·30페이지까지 지원하고, 초과분은 자동으로 분할 처리됩니다. 큰 문서도 변환이 끊기지 않습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.features[4]")]},
    ],
    "역설·반전": [
        {"suffix": "ToS안전", "program": "sci",
         "headline": "다 자동화해도, 마지막 버튼은 안 누릅니다",
         "body": "투고 직전까지 자동화하고 Submit 버튼만 저자가 직접 누르는 ToS-안전 설계입니다. 일부러 멈췄습니다.",
         "cta": "저널 매칭은 무료로 시작",
         "evidence": [_e("programs.sci.differentiators[1]"), _e("programs.sci.hooks_ko.thread[1]")]},
        {"suffix": "정직취소", "program": "paper",
         "headline": "데이터가 부족하면, 오히려 그렇게 씁니다",
         "body": "실측을 못 구하면 '못 구했다'고 그대로 적는 '정직 취소' 라벨. 감추는 대신 드러내는 쪽을 택했습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.hooks_ko.thread[2]")]},
        {"suffix": "자체채점", "program": "hwp",
         "headline": "완벽해 보일수록, 저희가 먼저 의심합니다",
         "body": "변환 결과를 SSIM으로 자체 채점하는 검증 구조입니다. 원본과 달라지면 결과물이 스스로 알려줍니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.differentiators[2]"), _e("programs.hwp.hooks_ko.thread[1]")]},
    ],
    "부정형": [
        {"suffix": "수식보존", "program": "hwp",
         "headline": "수식을 이미지로 바꾸지 마세요",
         "body": "변환 후에도 수식은 편집 가능한 OMML 객체로 남습니다. 이미지로 굳혀서 다시 손볼 필요가 없습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.differentiators[1]"), _e("programs.hwp.differentiators[0]")]},
        {"suffix": "논문시간", "program": "paper",
         "headline": "빈 페이지 앞에서 밤새우지 마세요",
         "body": "질의 한 줄로 지배방정식 도출부터 논문 초안까지 자동으로 나옵니다. 그 시간을 손으로 채우지 않아도 됩니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.pain_ko"), _e("programs.paper.features[0]"), _e("programs.paper.features[1]")]},
        {"suffix": "제안서시간", "program": "biz",
         "headline": "제안서 마감 전날, 밤새지 마세요",
         "body": "RFP 파일 하나면 Win Theme 3종과 근거 있는 KPI, 채널별 카피까지 자동으로 구조화됩니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.biz.pain_ko"), _e("programs.biz.hooks_ko.thread[0]")]},
    ],
    "정체성호명": [
        {"suffix": "연구자호명", "program": "paper",
         "headline": "대학원생과 연구원을 위해 만들었습니다",
         "body": "SCI Q1 11절 자동 심사 루프를 거쳐 편집 가능한 수식과 참고문헌이 정리된 논문 초안을 받습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.features[3]"), _e("programs.paper.features[4]")]},
        {"suffix": "제안팀호명", "program": "biz",
         "headline": "다음 입찰 준비하는 동료에게",
         "body": "제안요청서(RFP) 하나로 경제성·안전성·법률 적합성 분석까지 포함된 제안서 리포트가 나옵니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.biz.sends_ko[0]"), _e("programs.biz.features[1]")]},
        {"suffix": "변환동료호명", "program": "hwp",
         "headline": "한글 파일과 싸우는 동료에게",
         "body": "HWPX·DOCX·PDF 변환에서 수식은 편집 가능한 객체로, 표와 스타일은 그대로 보존됩니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.sends_ko[0]"), _e("programs.hwp.differentiators[0]")]},
    ],
    "시간압박": [
        {"suffix": "논문마감", "program": "paper",
         "headline": "다음 학기 마감인데, 아직 초안이 없다면",
         "body": "자연어 질의 한 줄이면 결합 지배방정식 도출부터 편집 가능한 수식이 담긴 논문 초안까지 자동으로 나옵니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.sends_ko[2]"), _e("programs.paper.features[0]")]},
        {"suffix": "투고마감", "program": "sci",
         "headline": "졸업 논문 투고 앞둔 후배에게, 지금",
         "body": "제목·초록·키워드만 넣으면 Q1 여부·게재비·심사기간까지 붙은 저널 후보가 무료로 나옵니다.",
         "cta": "저널 매칭은 무료로 시작",
         "evidence": [_e("programs.sci.sends_ko[1]"), _e("programs.sci.hooks_ko.thread[0]")]},
        {"suffix": "특허마감", "program": "biz",
         "headline": "특허 기획 고민, 마감 전에 정리하세요",
         "body": "제안서 하나에서 특허기획(TRIZ)·명세서·IR 피치덱까지 옵션으로 확장됩니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.biz.sends_ko[2]"), _e("programs.biz.features[4]")]},
    ],
    "호기심갭": [
        {"suffix": "투고패키지", "program": "sci",
         "headline": "포털에 넣을 파일, 이미 준비돼 있습니다",
         "body": "저자 정보와 추천 리뷰어까지 정리한 투고 패키지를 내려받을 수 있습니다. 무엇이 담겼는지는 열어보면 압니다.",
         "cta": "저널 매칭은 무료로 시작",
         "evidence": [_e("programs.sci.hooks_ko.thread[2]")]},
        {"suffix": "자체점수", "program": "hwp",
         "headline": "이 변환기, 자기 점수를 스스로 매깁니다",
         "body": "SSIM 기반으로 변환 정합도를 자체 확인하는 검증 구조입니다. 몇 점인지는 결과물에 함께 나옵니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.differentiators[2]"), _e("programs.hwp.hooks_ko.thread[1]")]},
        {"suffix": "리포트5종", "program": "biz",
         "headline": "제안서 하나에서 리포트 5종이 나왔습니다",
         "body": "체크박스 몇 개로 제안서·특허기획·명세서·IR 피치덱까지 확장됩니다. 무엇을 눌렀는지는 후기에 있습니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.biz.hooks_ko.thread[1]")]},
    ],
    "결과선공개": [
        {"suffix": "논문과정", "program": "paper",
         "headline": "질의 한 줄이 초안이 되는 과정을 공개합니다",
         "body": "자연어 질의 → 지배방정식 자동 도출 → 4축 검증과 SCI Q1 심사 루프 → 편집 가능한 논문 초안, "
                 "이 순서 그대로입니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.paper.features[0]"), _e("programs.paper.features[1]"),
                      _e("programs.paper.features[3]"), _e("programs.paper.features[4]")]},
        {"suffix": "전략설계", "program": "biz",
         "headline": "키워드 10개 추출 후 나온 건 전략 문서였습니다",
         "body": "핵심 키워드 추출로 타겟·채널·메시지 전략까지 설계된 결과를 그대로 보여드립니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.biz.hooks_ko.blog[2]"), _e("programs.biz.features[2]")]},
        {"suffix": "그림추출", "program": "hwp",
         "headline": "PDF 그림을 뽑아 문서에 다시 심는 순서입니다",
         "body": "PDF 속 그림과 도식을 추출해 결과 문서에 그대로 재삽입합니다. 캡처해서 붙여넣던 작업이 사라집니다.",
         "cta": "가입 즉시 무료 체험",
         "evidence": [_e("programs.hwp.features[3]"), _e("programs.hwp.hooks_ko.thread[2]")]},
    ],
}

for _t, _items in POOL.items():
    assert len(_items) == 3, f"POOL[{_t}] must have exactly 3 items"


# --------------------------------------------------------------------------
# 8b. English content pool — same 8 hook types x 3 items, same (hook_type,
# suffix) pairing as POOL above, but this is NOT a translation of the KO
# winner copy: each item is authored directly in English and cited against
# products.json's own English fields (hooks_en / differentiators_en /
# pain_en / sends_en / name_en) wherever those exist. Where no EN field
# exists for a specific numeric fact (e.g. the KRW price, the 20MB/30-page
# limit, the exact 47-format count), the evidence string says so explicitly
# ("translated from KO; no EN field") and the number itself is carried over
# unchanged (never converted/invented) from the KO field it cites.
# ==========================================================================

POOL_EN: dict[str, list[dict]] = {
    "질문형": [
        {"suffix": "authority", "program": "paper",
         "headline": "Rejected 3 times by a virtual reviewer?",
         "body": "A built-in Q1 reviewer checks math, experiments, statistics, and the document, "
                 "then sends it back until it holds up.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.hooks_en.short[1]"), _e("programs.paper.hooks_en.thread[0]")]},
        {"suffix": "equation_trust", "program": "paper",
         "headline": "47 equations - really unbroken?",
         "body": "One sentence in, and back comes a draft with 47 editable equations. Open it and "
                 "check for yourself.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.hooks_en.thread[0]")]},
        {"suffix": "journal_search", "program": "sci",
         "headline": "Still hunting for a journal, one by one?",
         "body": "Paste your title, abstract, and keywords - get candidate journals with quartile, SJR, "
                 "APC, and review time, free.",
         "cta": "Start free matching",
         "evidence": [_e("programs.sci.hooks_en.thread[0]"), _e("programs.sci.differentiators_en[0]")]},
    ],
    "숫자형": [
        {"suffix": "price", "program": "paper",
         "headline": "₩4,100, 47 equations, 3 reviews",
         "body": "Starting at ₩4,100 per call, a virtual reviewer sends it back 3 times before you get "
                 "a draft with 47 editable equations.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.price_ko (KRW figure carried over; no EN price field)"),
                      _e("programs.paper.hooks_en.thread[0]")]},
        {"suffix": "format_count", "program": "hwp",
         "headline": "47 formats, from ₩2,800 a call",
         "body": "Convert across 47 formats - HWPX, DOCX, PDF and more - starting at ₩2,800 per call.",
         "cta": "Start free trial",
         "evidence": [_e("programs.hwp.features[0] (translated from KO; no EN field)"),
                      _e("programs.hwp.price_ko (KRW figure carried over; no EN price field)")]},
        {"suffix": "size_limit", "program": "hwp",
         "headline": "20MB, 30 pages - then auto-split",
         "body": "Files up to 20MB and 30 pages convert directly; anything larger is split "
                 "automatically so it never stalls.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.features[4] (translated from KO; no EN field)")]},
    ],
    "역설·반전": [
        {"suffix": "tos_safe", "program": "sci",
         "headline": "Automated - except the last click",
         "body": "Everything up to submission runs on its own; you press Submit yourself. "
                 "A ToS-safe design, on purpose.",
         "cta": "Start free matching",
         "evidence": [_e("programs.sci.differentiators_en[1]")]},
        {"suffix": "honest_gap", "program": "paper",
         "headline": "Can't find the data? We say so.",
         "body": "When real measurements aren't available, the draft says so instead of hiding it - "
                 "labeling its own validation gaps.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.hooks_en.blog[1]")]},
        {"suffix": "self_grade", "program": "hwp",
         "headline": "The more perfect it looks, we doubt it",
         "body": "Every conversion self-grades its own fidelity with SSIM. If it drifts from the "
                 "original, the output tells you.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.differentiators_en[2]"), _e("programs.hwp.hooks_en.thread[0]")]},
    ],
    "부정형": [
        {"suffix": "equation_preserve", "program": "hwp",
         "headline": "Don't let your equations become images",
         "body": "Equations stay editable objects after conversion, never flattened into images - "
                 "nothing to fix afterward.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.differentiators_en[1]"), _e("programs.hwp.differentiators_en[0]")]},
        {"suffix": "paper_time", "program": "paper",
         "headline": "Don't stare at a blank page all night",
         "body": "One natural-language query derives the governing equations and drafts the paper, "
                 "so you don't fill that time by hand.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.pain_en"), _e("programs.paper.differentiators_en[0]")]},
        {"suffix": "proposal_time", "program": "biz",
         "headline": "No all-nighter before the deadline",
         "body": "Upload one RFP and get 3 Win Themes, KPI rationale, and channel-ready copy, "
                 "automatically.",
         "cta": "Start free now",
         "evidence": [_e("programs.biz.pain_en"), _e("programs.biz.hooks_en.thread[0]")]},
    ],
    "정체성호명": [
        {"suffix": "researcher", "program": "paper",
         "headline": "Built for grad students and researchers",
         "body": "A built-in Q1 reviewer checks your work, then returns a draft with editable "
                 "equations and a reference list.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.differentiators_en[0]"), _e("programs.paper.sends_en[2]")]},
        {"suffix": "proposal_team", "program": "biz",
         "headline": "For your proposal team, next bid",
         "body": "One RFP upload turns into economic, safety, and legal analysis backing up "
                 "your proposal.",
         "cta": "Start free now",
         "evidence": [_e("programs.biz.sends_en[0]"), _e("programs.biz.differentiators_en[2]")]},
        {"suffix": "conversion_colleague", "program": "hwp",
         "headline": "For the colleague fighting HWP files",
         "body": "Equations stay editable, and tables and styles survive the conversion untouched.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.sends_en[0]"), _e("programs.hwp.differentiators_en[0]")]},
    ],
    "시간압박": [
        {"suffix": "paper_deadline", "program": "paper",
         "headline": "Deadline next term, still no draft?",
         "body": "One natural-language query derives the governing equations and drafts a paper "
                 "with editable equations, automatically.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.sends_en[2]"), _e("programs.paper.pain_en")]},
        {"suffix": "submission_deadline", "program": "sci",
         "headline": "For a labmate about to submit, now",
         "body": "Paste your title, abstract, and keywords for journal candidates with quartile, "
                 "APC, and review time, free.",
         "cta": "Start free matching",
         "evidence": [_e("programs.sci.sends_en[1]"), _e("programs.sci.hooks_en.thread[0]")]},
        {"suffix": "patent_deadline", "program": "biz",
         "headline": "Sort out patent planning before the deadline",
         "body": "One proposal scales into patent planning (TRIZ), a spec, and an IR pitch deck "
                 "as options.",
         "cta": "Start free now",
         "evidence": [_e("programs.biz.differentiators_en[1]")]},
    ],
    "호기심갭": [
        {"suffix": "submission_package", "program": "sci",
         "headline": "Your submission package is already built",
         "body": "Author details and suggested reviewers come packaged for the portal - "
                 "what's inside is worth opening.",
         "cta": "Start free matching",
         "evidence": [_e("programs.sci.hooks_ko.thread[2] (translated from KO; no EN field)")]},
        {"suffix": "self_score", "program": "hwp",
         "headline": "This converter grades its own score",
         "body": "Fidelity is self-checked with SSIM after every conversion. The score comes back "
                 "with the result.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.differentiators_en[2]"), _e("programs.hwp.hooks_en.thread[0]")]},
        {"suffix": "five_reports", "program": "biz",
         "headline": "One proposal turned into 5 reports",
         "body": "A few checkboxes extend it into a proposal, patent plan, spec, and IR pitch deck - "
                 "what got checked is in the writeup.",
         "cta": "Start free now",
         "evidence": [_e("programs.biz.differentiators_en[1]")]},
    ],
    "결과선공개": [
        {"suffix": "paper_process", "program": "paper",
         "headline": "The process from query to draft, shown",
         "body": "Query -> governing equations -> 4-axis validation and Q1 review -> a draft with "
                 "editable equations. That's the order.",
         "cta": "Start free now",
         "evidence": [_e("programs.paper.differentiators_en[0]"), _e("programs.paper.hooks_en.short[1]")]},
        {"suffix": "strategy_design", "program": "biz",
         "headline": "Keywords in, a strategy doc came out",
         "body": "Keyword extraction feeds straight into target, channel, and message strategy - "
                 "shown as it happened.",
         "cta": "Start free now",
         "evidence": [_e("programs.biz.features[2] (translated from KO; no EN field)")]},
        {"suffix": "figure_extract", "program": "hwp",
         "headline": "How figures move from PDF to draft",
         "body": "Figures and diagrams are extracted from the PDF and reinserted into the output "
                 "document - copy-paste work goes away.",
         "cta": "Start free now",
         "evidence": [_e("programs.hwp.features[3] (translated from KO; no EN field)")]},
    ],
}

for _t, _items in POOL_EN.items():
    assert len(_items) == 3, f"POOL_EN[{_t}] must have exactly 3 items"
assert set(POOL_EN.keys()) == set(POOL.keys()), "POOL_EN hook types must match POOL"


# ==========================================================================
# 9. largest-remainder apportionment (research distribution -> 18 seats,
#    capped by pool size 3/type, with logged overflow redistribution)
# ==========================================================================

def largest_remainder_apportion(shares: dict[str, float], total_seats: int) -> dict[str, int]:
    keys = list(shares.keys())
    total_weight = sum(shares.values())
    if total_weight <= 0 or not keys:
        base = total_seats // max(len(keys), 1)
        seats = {k: base for k in keys}
        rem = total_seats - base * len(keys)
        for k in keys[:rem]:
            seats[k] += 1
        return seats
    quotas = {k: total_seats * (w / total_weight) for k, w in shares.items()}
    seats = {k: int(math.floor(q)) for k, q in quotas.items()}
    assigned = sum(seats.values())
    remainder_order = sorted(keys, key=lambda k: quotas[k] - seats[k], reverse=True)
    i = 0
    while assigned < total_seats and remainder_order:
        k = remainder_order[i % len(remainder_order)]
        seats[k] += 1
        assigned += 1
        i += 1
    return seats


def allocate_with_pool_caps(target_seats: dict[str, int], pool_sizes: dict[str, int],
                             share_order: list[str], total_seats: int) -> tuple[dict[str, int], list[str]]:
    notes = []
    taken = {t: 0 for t in share_order}
    overflow = 0
    for t in share_order:
        cap = pool_sizes.get(t, 0)
        want = target_seats.get(t, 0)
        give = min(want, cap)
        taken[t] = give
        if want > cap:
            overflow += want - cap
            notes.append(
                f"{t}: 관측 비중 기준 목표 {want}개가 보유 문구 풀({cap}개)을 초과 -> "
                f"{want - cap}개를 차순위 유형으로 재배분"
            )
    if overflow > 0:
        for t in share_order:
            if overflow <= 0:
                break
            avail = pool_sizes.get(t, 0) - taken.get(t, 0)
            if avail > 0:
                give = min(avail, overflow)
                taken[t] += give
                overflow -= give
                notes.append(f"  -> {t}에서 {give}개 추가로 채움 (재배분 대상)")
    total_taken = sum(taken.values())
    if total_taken < total_seats:
        # safety fallback: fill any remaining capacity in share order
        for t in share_order:
            if total_taken >= total_seats:
                break
            avail = pool_sizes.get(t, 0) - taken.get(t, 0)
            if avail > 0:
                give = min(avail, total_seats - total_taken)
                taken[t] += give
                total_taken += give
                notes.append(f"  -> 목표 총합 부족분 {give}개를 {t}에서 추가 충당")
    return taken, notes


# ==========================================================================
# 10. subcommand: seeds
# ==========================================================================

def _char_len_check(item_id: str, headline: str, body: str, cta: str) -> list[str]:
    problems = []
    if len(headline) > 40:
        problems.append(f"{item_id}: headline {len(headline)}자 > 40자")
    if len(body) > 120:
        problems.append(f"{item_id}: body {len(body)}자 > 120자")
    if len(cta) > 20:
        problems.append(f"{item_id}: cta {len(cta)}자 > 20자")
    return problems


def _forbidden_word_check(item_id: str, text: str, products: dict, program: str) -> list[str]:
    problems = []
    for w in products.get("forbidden_words_global", []):
        if w in text:
            problems.append(f"{item_id}: 전역 금지어 '{w}' 포함")
    prog = products.get("programs", {}).get(program, {})
    for w in prog.get("forbidden_words", []):
        if w in text:
            problems.append(f"{item_id}: {program} 금지어 '{w}' 포함")
    return problems


# minimum signal (videos) required in a language subset before `seeds` trusts
# it over the pooled (all-query) distribution — below this, EN (or KO) falls
# back to the pooled distribution with a logged note, per spec.
MIN_LANG_VIDEOS = 5


def _seeds_path_for_lang(lang: str) -> Path:
    return PROJECT_ROOT / "copy" / f"seed_variants_{lang}.json"


def _build_seeds_for_lang(lang: str, yh: dict, products: dict, log) -> dict:
    """Returns the full out_obj to write to copy/seed_variants_<lang>.json,
    or raises ResearchError on validation failure."""
    pool = POOL if lang == "ko" else POOL_EN
    hook_freq_lang = yh.get("hook_type_freq_by_lang", {}).get(lang, [])
    n_records_lang = yh.get("meta", {}).get("n_records_by_lang", {}).get(lang, 0)
    used_fallback = False

    if n_records_lang < MIN_LANG_VIDEOS or not hook_freq_lang:
        log(f"[{lang}] language subset too small ({n_records_lang} videos < {MIN_LANG_VIDEOS}) "
            f"-> falling back to pooled (all-query) hook_type_freq")
        hook_freq = yh.get("hook_type_freq", [])
        used_fallback = True
    else:
        hook_freq = hook_freq_lang

    shares = {row["hook_type"]: row["weighted_views_per_day"] for row in hook_freq if row["hook_type"] in pool}
    for t in pool:
        shares.setdefault(t, 0.0)

    share_order = sorted(pool.keys(), key=lambda t: shares.get(t, 0.0), reverse=True)
    pool_sizes = {t: len(items) for t, items in pool.items()}
    total_seats = 18

    targets = largest_remainder_apportion(shares, total_seats)
    taken, notes = allocate_with_pool_caps(targets, pool_sizes, share_order, total_seats)
    if used_fallback:
        notes.insert(0, f"{lang}: EN/KO 쿼리 서브셋 표본 부족({n_records_lang}개 영상) -> 전체(pooled) 분포로 대체")
    for n in notes:
        log(f"[apportion:{lang}] {n}")

    seeds = []
    problems = []
    idx = 0
    for t in share_order:
        n = taken.get(t, 0)
        items = pool[t][:n]
        for item in items:
            idx += 1
            seed_id = f"seed_{idx:02d}_{lang}_{slugify(t)}_{slugify(item['suffix'])}"
            source_evidence = (
                f"youtube_hooks.json[{'pooled (fallback)' if used_fallback else lang}]: "
                f"훅유형 '{t}' 가중 비중 {shares.get(t, 0.0):.1f} views/day "
                f"(share_pct_by_views 기준 apportion) -> 구조 템플릿 '{TEMPLATE_TEXT[t]}' 적용"
            )
            seed = {
                "id": seed_id,
                "lang": lang,
                "headline": item["headline"],
                "body": item["body"],
                "cta": item["cta"],
                "angle": f"{t}-{item['suffix']}",
                "hook_type": t,
                "hook_template": TEMPLATE_TEXT[t],
                "source_evidence": source_evidence,
                "evidence": item["evidence"],
                "products_program": item["program"],
            }
            problems += _char_len_check(seed_id, seed["headline"], seed["body"], seed["cta"])
            full_text = f"{seed['headline']} {seed['body']} {seed['cta']}"
            problems += _forbidden_word_check(seed_id, full_text, products, item["program"])
            seeds.append(seed)

    if problems:
        for p in problems:
            log(f"  ! VALIDATION FAILED: {p}")
        raise ResearchError(f"{len(problems)} {lang} seed(s) failed validation")

    if len(seeds) != 18:
        raise ResearchError(f"expected exactly 18 {lang} seeds, built {len(seeds)}")

    return {
        "_generated_at": datetime.now().isoformat(timespec="seconds"),
        "_generated_from": "research/out/youtube_hooks.json",
        "_lang": lang,
        "_used_pooled_fallback": used_fallback,
        "_n_language_records": n_records_lang,
        "_apportionment_notes": notes,
        "_hook_type_targets": targets,
        "_hook_type_taken": taken,
        "variants": seeds,
    }


def cmd_seeds(args) -> int:
    def log(msg):
        print(msg, file=sys.stderr)

    yh_path = OUT_DIR / "youtube_hooks.json"
    if not yh_path.exists():
        log(f"[SKIP] {yh_path} 가 없습니다. 먼저 `python hook_research.py youtube` 를 실행하세요.\n"
            f"       기존 seed_variants_*.json 은 그대로 둡니다 (변경 없음).")
        return 1

    yh = load_json(yh_path)
    products = load_json(PRODUCTS_JSON)
    langs = ["ko", "en"] if args.lang == "both" else [args.lang]

    for lang in langs:
        out_obj = _build_seeds_for_lang(lang, yh, products, log)
        path = _seeds_path_for_lang(lang)
        dump_json(path, out_obj)
        log(f"wrote {path} ({len(out_obj['variants'])} seeds, hook-type mix: {out_obj['_hook_type_taken']}, "
            f"pooled_fallback={out_obj['_used_pooled_fallback']})")
    return 0


# ==========================================================================
# main
# ==========================================================================

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="subcommand", required=True)

    yt = sub.add_parser("youtube", help="pull + classify real YouTube search metadata")
    yt.add_argument("--queries", default=str(HERE / "queries.json"))
    yt.add_argument("--limit", type=int, default=15, help="results per query (yt-dlp ytsearch<limit>)")
    yt.add_argument("--timeout-s", type=int, default=300)
    yt.add_argument("--refresh", action="store_true", help="ignore per-query raw cache, refetch")
    yt.add_argument("--use-llm", action="store_true",
                     help="also send ambiguous ('기타') titles to `claude -p --json-schema` "
                          "(PAID — off by default)")
    yt.add_argument("--model", default=None)
    yt.add_argument("--max-budget-usd", type=float, default=1.0)
    yt.set_defaults(func=cmd_youtube)

    ig = sub.add_parser("instagram", help="honest [SKIP] + research/inbox/*.csv ingest")
    ig.set_defaults(func=cmd_instagram)

    sd = sub.add_parser("seeds", help="(re)build copy/seed_variants_<lang>.json from youtube_hooks.json")
    sd.add_argument("--lang", choices=["ko", "en", "both"], default="both")
    sd.set_defaults(func=cmd_seeds)

    return ap


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        return args.func(args)
    except ResearchError as e:
        print(f"FATAL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
