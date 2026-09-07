#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_backup.py — 홍보문구 최적화 산출물 백업 패키저 (2026-09-01)

무엇을 담나
  1) 최적화 리포트 : FINAL_REPORT.md/.json (ko/en), COMPARISON.md, 세대별 원시 판정
  2) 영상          : 22초 릴스 KO/EN mp4
  3) 설명문        : 유튜브/인스타 설명문 KO/EN
  4) 재현용 코드   : evolve.py, run_copy_harness.py, copy_schemas.py, 시드, 페르소나 표본

왜 코드와 표본까지 담나
  리포트의 숫자는 (코드, 시드, 표본, seed=42) 네 가지가 갖춰져야 재현된다. 리포트만
  백업하면 6개월 뒤 "이 점수가 어디서 나왔나"에 답할 수 없다. 용량이 작으므로 함께 담는다.

메일 첨부 상한(25MB) 때문에 zip 을 두 벌 만든다.
  full  : 전부
  light : 영상 제외(리포트·설명문·코드만) — 첨부가 25MB 를 넘을 때 쓰는 대안
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]          # .../홍보문구최적화
PROMO = ROOT.parent                                  # .../0 홍보자동화


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024.0
    return f"{n:.1f}GB"


def collect(results_dir: Path) -> dict[str, list[Path]]:
    """카테고리별 실제 존재하는 파일만 모은다. 없는 파일은 조용히 빼지 않고 호출부가 보고한다."""
    groups: dict[str, list[Path]] = {}

    rep: list[Path] = []
    for pat in ("FINAL_REPORT.md", "FINAL_REPORT.json", "COMPARISON.md"):
        rep += sorted(results_dir.rglob(pat))
    # 세대별 원시 판정(report.json)은 근거이므로 함께 담는다
    rep += sorted(results_dir.rglob("report.json"))
    groups["최적화 리포트"] = rep

    groups["영상"] = sorted((ROOT / "video").glob("릴스_*.mp4"))
    groups["설명문"] = sorted((ROOT / "descriptions").glob("*.md")) + \
                       sorted((ROOT / "descriptions").glob("*.txt"))

    code = [ROOT / "optimize" / "evolve.py",
            ROOT / "harness" / "run_copy_harness.py",
            ROOT / "harness" / "copy_schemas.py",
            ROOT / "data" / "filter_personas.py",
            ROOT / "research" / "hook_research.py",
            ROOT / "copy" / "seed_variants_ko.json",
            ROOT / "copy" / "seed_variants_en.json",
            ROOT / "data" / "personas_kr_25_filtered.jsonl",
            ROOT / "data" / "personas_us_25_filtered.jsonl"]
    code += sorted((ROOT / "video").glob("build_copy_reel_22s.py"))
    groups["재현용 코드·표본"] = [p for p in code if p.exists()]
    return groups


def write_zip(dst: Path, groups: dict[str, list[Path]], skip: set[str]) -> tuple[int, int]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for cat, files in groups.items():
            if cat in skip:
                continue
            for p in files:
                try:
                    z.write(p, arcname=str(Path(cat) / p.relative_to(ROOT)))
                except ValueError:
                    z.write(p, arcname=str(Path(cat) / p.name))
                n += 1
    return n, dst.stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", required=True, type=Path, help="최적화 결과 디렉토리")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "backup")
    ap.add_argument("--stamp", default=None, help="파일명 타임스탬프(기본: 현재시각)")
    a = ap.parse_args()

    if not a.results.exists():
        print(f"[중단] 결과 디렉토리가 없습니다: {a.results}")
        return 1

    stamp = a.stamp or datetime.now().strftime("%Y%m%d_%H%M")
    groups = collect(a.results)

    print("[백업 대상]")
    total = 0
    for cat, files in groups.items():
        size = sum(p.stat().st_size for p in files)
        total += size
        print(f"  {cat:<16} {len(files):>3}개  {human(size):>9}")
        for p in files[:6]:
            print(f"      {p.relative_to(ROOT) if ROOT in p.parents else p.name}  ({human(p.stat().st_size)})")
        if len(files) > 6:
            print(f"      ... 외 {len(files)-6}개")
    print(f"  {'합계':<16} {sum(len(v) for v in groups.values()):>3}개  {human(total):>9}")

    empty = [c for c, v in groups.items() if not v]
    if empty:
        print(f"\n[주의] 비어 있는 항목: {', '.join(empty)} — 해당 산출물이 아직 없습니다.")

    full = a.out_dir / f"홍보문구최적화_백업_{stamp}.zip"
    light = a.out_dir / f"홍보문구최적화_백업_{stamp}_경량_영상제외.zip"
    n1, s1 = write_zip(full, groups, skip=set())
    n2, s2 = write_zip(light, groups, skip={"영상"})

    print("\n[생성된 백업]")
    print(f"  전체   {full}")
    print(f"         {n1}개 파일 / {human(s1)}")
    print(f"  경량   {light}")
    print(f"         {n2}개 파일 / {human(s2)}  (영상 제외)")

    LIMIT = 25 * 1024 * 1024
    print("\n[메일 첨부 판정] 상한 25MB")
    for label, path, size in (("전체", full, s1), ("경량", light, s2)):
        ok = size <= LIMIT
        print(f"  {label}: {human(size)} -> {'첨부 가능' if ok else '초과, 첨부 불가'}")

    manifest = a.out_dir / f"홍보문구최적화_백업_{stamp}_목록.json"
    manifest.write_text(json.dumps({
        "stamp": stamp,
        "results_dir": str(a.results),
        "zip_full": str(full), "zip_full_bytes": s1,
        "zip_light": str(light), "zip_light_bytes": s2,
        "groups": {c: [str(p) for p in v] for c, v in groups.items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n  목록   {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
