#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filter_personas.py — 광고 문구 판정용 표본 필터 (2026-09-01)

왜 필요한가(실측 근거):
  무작위 표본을 그대로 쓰면 광고 문구 판정에 노이즈가 섞인다. 실제로 US 25명 무작위
  표본의 1번 행이 신생아(age=0, occupation=not_in_workforce) 였다. 신생아에게
  "이 광고를 보고 클릭하겠는가"를 물어 얻은 답은 문구의 우열을 가리는 데 쓸 수 없다.

무엇을 거르나 — 두 단계:
  1) 성인·경제활동 게이트: age >= 22, 취업/학업 상태(무직·not_in_workforce 제외)
  2) 도달 가능성 게이트: 고등교육 이상 또는 연구·교육·기술·전문직 직업

무엇을 거르지 않나(중요):
  "PDE 논문 쓰는 사람"으로 좁히지 않는다. 그렇게 하면 자기 제품에 딱 맞게 만든
  페르소나가 좋다고 답하는 동어반복이 된다(sibling 하네스의 illustrative_construction
  5명이 5/5로 나온 것과 같은 함정). 여기서 원하는 건 "이 광고가 실제로 노출될 만한
  성인 모집단"이지 "확실한 고객"이 아니다.

정직성: 필터를 걸었다는 사실과 통과율을 산출물 메타에 남긴다. 리포트에서 이 표본을
인용할 때는 반드시 "필터링된 표본"이라고 밝혀야 한다.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

# --- 성인 기준 ---
MIN_AGE = 22

# --- 비경제활동/제외 직업 토큰(한/영) ---
EXCLUDE_OCC = (
    "not_in_workforce", "unemployed", "무직", "학생",  # 학생은 아래 EDU 게이트에서 별도 취급
)

# --- 고등교육 토큰(한/영) ---
HIGHER_EDU = (
    "bachelors", "masters", "doctorate", "professional_degree", "some_college", "associates",
    "4년제 대학교", "2~3년제 대학", "대학원", "석사", "박사", "전문대",
)

# --- 연구·교육·기술·전문직 토큰(한/영) ---
PRO_OCC = (
    "engineer", "scientist", "researcher", "professor", "teacher", "physician", "analyst",
    "developer", "programmer", "technician", "architect", "pharmacist", "chemist",
    "statistician", "mathematic", "librar", "postsecondary", "医",  # noqa
    "연구", "공학", "기술자", "기술사", "교수", "교사", "강사", "개발자", "프로그래머",
    "설계", "분석", "의사", "약사", "수의사", "회계사", "변리사", "변호사", "건축",
    "엔지니어", "전문가", "학예사", "사서",
)

STEM_FIELD = ("stem", "자연과학", "공학", "의약", "수학", "정보", "computer", "engineering", "science")


def _has(text, tokens):
    t = (text or "").lower()
    return any(tok.lower() in t for tok in tokens)


def passes(row: dict) -> tuple[bool, str]:
    """(통과여부, 사유). 사유는 통계·감사를 위해 남긴다."""
    age = row.get("age")
    if not isinstance(age, int) or age < MIN_AGE:
        return False, f"age<{MIN_AGE}({age})"

    occ = str(row.get("occupation") or "")
    if _has(occ, EXCLUDE_OCC) and not _has(occ, PRO_OCC):
        return False, f"비경제활동({occ[:24]})"

    edu = str(row.get("education_level") or "")
    field = str(row.get("bachelors_field") or "")

    if _has(occ, PRO_OCC):
        return True, "전문·연구·기술직"
    if _has(edu, HIGHER_EDU):
        return True, f"고등교육({edu})"
    if _has(field, STEM_FIELD):
        return True, f"STEM 전공({field})"
    return False, f"도달가능성 미달(edu={edu[:16]}, occ={occ[:20]})"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, required=True, help="입력 JSONL(대형 표본)")
    ap.add_argument("--out", type=Path, required=True, help="출력 JSONL(필터 통과 n명)")
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--stats", type=Path, default=None, help="통과율 통계 JSON 저장 경로")
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.src.open(encoding="utf-8") if l.strip()]
    kept, reasons = [], {}
    for r in rows:
        ok, why = passes(r)
        key = why.split("(")[0]
        reasons[key] = reasons.get(key, 0) + 1
        if ok:
            kept.append(r)

    rng = random.Random(args.seed)
    rng.shuffle(kept)
    sample = kept[: args.n]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for i, r in enumerate(sample):
            r = dict(r)
            r["idx"] = i
            r["_filtered"] = True
            r["_filter_rule"] = f"age>={MIN_AGE} AND (전문·연구·기술직 OR 고등교육 OR STEM전공)"
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    stats = {
        "src": str(args.src), "out": str(args.out),
        "n_in": len(rows), "n_pass": len(kept), "pass_rate_pct": round(100 * len(kept) / max(1, len(rows)), 1),
        "n_sampled": len(sample), "seed": args.seed, "reasons": reasons,
        "rule": f"age>={MIN_AGE} AND (전문·연구·기술직 OR 고등교육 OR STEM전공)",
    }
    if args.stats:
        args.stats.parent.mkdir(parents=True, exist_ok=True)
        args.stats.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))
    if len(sample) < args.n:
        print(f"[WARN] 요청 {args.n}명 중 {len(sample)}명만 확보 — 원본 표본을 늘리십시오")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
