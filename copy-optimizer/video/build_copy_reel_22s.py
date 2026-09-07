#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
홍보문구최적화/video/build_copy_reel_22s.py
IDEAINNOV.COM 홍보 카피 최적화 결과 — 22.00초 세로 릴스 빌더 (KO/EN, 2026-09-01)
================================================================================
optimize/evolve.py가 진화시킨 홍보 카피(winning_variant, 또는 그걸 담은
FINAL_REPORT.json)를 --copy-json으로 받아, 가상인구페르소나/promo/video/
build_persona_reel_22s.py의 구조와 실측 교훈을 그대로 미러링한 22.0초 세로
릴스로 렌더링한다.

문구(headline/body/cta)는 --copy-json이 준 그대로만 쓰고, 그 밖의 모든 사실
(가격·형식 개수·기능 설명·URL)은 반드시 common/products.json 실측 값에서만
가져온다. products.json에 없는 숫자·가격·기능은 지어내지 않고 그 클레임을
통째로 버린다(요청 사양 그대로).

재사용(수정 금지, import만):
    가상인구페르소나/promo/video/build_persona_short.py 를 bps로:
        normalize / make_voice / mix_voice / dur_of / _spec_hash / run_encode /
        VOICE_KO / VOICE_EN / W·H·FPS / FFMPEG / FFPROBE / GPU_FF / run_utf8 /
        ROOT / video_encode_args(bps 경유)
    motion/mograph.py            — render_kinetic_title / render_stat_pop /
        render_before_after / render_screen_showcase + get_font/wrap_text/
        fit_text_block/draw_lines_centered/ease_out_back/ease_out_cubic/
        clamp01/new_rgba_frame/new_layer/render_to_video/SAFE_*/ACCENT/SUB/
        CANVAS_*/BG_TOP (render_brand_end는 이 파일에 새로 구현하되 전부
        mograph 프리미티브만 쓴다 — mograph.py 자체는 건드리지 않는다)
    common/tts_text.py            — to_spoken_ko (한국어 TTS 발음 정규화)
    common/qr_card.py             — save_qr_card / verify_scannable (QR PNG가
        없을 때만 쓰는 폴백 생성 경로)

concat / burn_subtitles / add_loop_tail 도 bps에서 그대로 재사용한다. 이
세 함수는 코드 내부에서 모듈 전역 이름 `WORK`를 직접 참조해 중간 산출물을
쓴다(bps.WORK == 가상인구페르소나/promo/video/.work). 아무 조치 없이 그대로
부르면 이번 작업 지시("홍보문구최적화/ 폴더 안에서만 쓴다")를 어기고 다른
서브프로젝트 폴더에 파일을 쓰게 된다. build_persona_short.py 자신도 정확히
같은 이유로 완성릴스/build_program_shorts.py의 헬퍼를 "복사"해서 재구현했지만
(그 파일 20~26행 주석), 우리는 그 정도까지 코드를 복제할 필요가 없다 —
WORK는 함수 정의 시점이 아니라 "호출 시점"에 bps 모듈 네임스페이스에서 조회되는
전역 변수이므로, import 직후 `bps.WORK = OUR_WORK_DIR` 한 줄만 재바인딩하면
소스 파일을 전혀 건드리지 않고도(런타임에 임포트된 모듈 객체의 속성 하나만
바꿀 뿐, .py 파일은 무수정) 안전하게 재사용할 수 있다.

읽기 전용 참고(수정 안 함, 구조만 미러링):
    가상인구페르소나/promo/video/build_persona_reel_22s.py
    (render_brand_end 레이아웃, QR 오버레이 ffmpeg 필터 패턴, 검증 파이프라인
    구조를 그대로 따라 했다.)

사용:
    PYTHONIOENCODING=utf-8 python build_copy_reel_22s.py --copy-json <path> --lang ko
    PYTHONIOENCODING=utf-8 python build_copy_reel_22s.py --copy-json <path> --lang en --out <path>
    PYTHONIOENCODING=utf-8 python build_copy_reel_22s.py --copy-json <path> --lang ko --verify-only
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

# 이 파일: .../홍보문구최적화/video/build_copy_reel_22s.py
# parents[0]=video, parents[1]=홍보문구최적화, parents[2]="0 홍보자동화"
_THIS_FILE = Path(__file__).resolve()
_PROMO_ROOT = _THIS_FILE.parents[2]                       # "0 홍보자동화"
_PERSONA_VIDEO_DIR = _PROMO_ROOT / "가상인구페르소나" / "promo" / "video"
sys.path.insert(0, str(_PERSONA_VIDEO_DIR))

import build_persona_short as bps  # noqa: E402  (import만 — main()은 __main__ 가드 안에 있어 안 돈다)

# 이 파일 전용 작업/출력 경로 — 홍보문구최적화/ 밖에는 아무 것도 쓰지 않는다.
OUT_DIR = _THIS_FILE.parent                               # .../홍보문구최적화/video
WORK = OUT_DIR / ".work_copy_reel22"
VERIFY_DIR = OUT_DIR / "_verify"
WORK.mkdir(parents=True, exist_ok=True)
VERIFY_DIR.mkdir(parents=True, exist_ok=True)

# bps.concat / bps.burn_subtitles / bps.add_loop_tail 이 참조하는 모듈 전역
# WORK를 이 폴더 밑으로 재바인딩한다(위 독스트링 설명 참고). bps.py 소스는
# 무수정 — 임포트된 모듈 객체의 속성만 런타임에 바꾼다.
bps.WORK = WORK

from motion import mograph  # noqa: E402  (bps 임포트 시점에 ROOT가 이미 sys.path에 들어감)
from common.tts_text import to_spoken_ko  # noqa: E402
from common.qr_card import save_qr_card, verify_scannable  # noqa: E402

from PIL import Image, ImageDraw  # noqa: E402

PRODUCTS_JSON_PATH = bps.ROOT / "common" / "products.json"
QR_PNG_DEFAULT = bps.ROOT / "기존영상 및 홍보자료" / "export" / "qr_ideainnov.png"
QR_URL = "https://ideainnov.com/?utm_source=qr"

# 산출물 파일명에 들어가는 날짜/판번호. 세대 2~4 이어받기 실행의 우승 문구로 다시 만든
# 결과이므로 gen4 를 붙인다 — 나중에 파일만 보고 어느 실행의 문구인지 알 수 있어야 한다.
TODAY = "2026-09-02_gen4"
DEFAULT_OUT_NAMES = {
    "ko": f"릴스_ideainnov_카피최적화_KO_22s_{TODAY}.mp4",
    "en": f"릴스_ideainnov_카피최적화_EN_22s_{TODAY}.mp4",
}

REQUIRED_VARIANT_KEYS = ("id", "lang", "headline", "body", "cta", "angle", "hook_type",
                          "evidence", "products_program")


def log(msg):
    print(f"[copy-reel22] {msg}", flush=True)


# ==============================================================================
# 입력 로딩 — winning_variant 단독 객체 또는 FINAL_REPORT.json 어느 쪽이든 허용
# ==============================================================================
def load_variant(copy_json_path: Path, expect_lang: str) -> dict:
    if not copy_json_path.exists():
        raise SystemExit(f"[FAIL] --copy-json 파일이 없습니다: {copy_json_path}")
    try:
        data = json.loads(copy_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"[FAIL] --copy-json JSON 파싱 실패: {copy_json_path} — {e}")

    if isinstance(data, dict) and "winning_variant" in data:
        variant = data["winning_variant"]
        if variant is None:
            raise SystemExit(
                f"[FAIL] {copy_json_path}: winning_variant가 null입니다"
                f"(이 언어 트랙 진화가 우승 문구를 찾지 못하고 끝났습니다) — 영상을 만들 수 없습니다."
            )
        log(f"입력 형식: FINAL_REPORT.json (winning_variant 추출, "
            f"score={data.get('winning_score')}, generation={data.get('winning_generation')})")
    elif isinstance(data, dict):
        variant = data
        log("입력 형식: 단일 variant 객체")
    else:
        raise SystemExit(f"[FAIL] --copy-json 최상위가 객체(dict)가 아닙니다: {copy_json_path}")

    missing = [k for k in REQUIRED_VARIANT_KEYS if k not in variant]
    if missing:
        raise SystemExit(
            f"[FAIL] {copy_json_path}: variant에 필수 키 누락 {missing} "
            f"(필요: {list(REQUIRED_VARIANT_KEYS)})"
        )

    if variant["lang"] != expect_lang:
        raise SystemExit(
            f"[FAIL] --lang {expect_lang} 로 요청했지만 copy-json의 variant.lang="
            f"{variant['lang']!r} 입니다 (id={variant.get('id')}). 언어가 일치하는 "
            f"copy-json을 넣거나 --lang을 바꾸십시오."
        )
    return variant


def load_products() -> dict:
    if not PRODUCTS_JSON_PATH.exists():
        raise SystemExit(f"[FAIL] products.json이 없습니다: {PRODUCTS_JSON_PATH}")
    return json.loads(PRODUCTS_JSON_PATH.read_text(encoding="utf-8"))


def get_product(products_data: dict, program_key: str) -> dict:
    programs = products_data.get("programs", {})
    if program_key not in programs:
        raise SystemExit(
            f"[FAIL] products.json에 programs.{program_key}가 없습니다 "
            f"(가능한 값: {list(programs.keys())}) — 이 프로그램의 사실을 확인할 수 없어 "
            f"영상을 만들 수 없습니다(수치·기능 발명 금지)."
        )
    return programs[program_key]


# ==============================================================================
# products.json evidence 경로 해석 — "programs.hwp.features[0]" 같은 문자열을
# 실제 값으로 되짚어, 카피가 근거로 댄 사실을 그대로 화면에 다시 쓸 수 있게 한다.
# (evidence 문자열 뒤에 "(설명)"이 붙어 있으면 그 부분은 무시한다)
# ==============================================================================
def resolve_evidence_path(products_data: dict, evidence_str: str):
    path = evidence_str.split(" ", 1)[0].strip()
    tokens = re.findall(r"[A-Za-z_]+|\[\d+\]", path)
    node = products_data
    for tok in tokens:
        if tok.startswith("["):
            idx = int(tok[1:-1])
            if not isinstance(node, list) or idx >= len(node):
                return None
            node = node[idx]
        else:
            if not isinstance(node, dict) or tok not in node:
                return None
            node = node[tok]
    return node


# 언어별로 "사용자가 실제로 사이트에서 하는 일"을 가장 잘 설명하는 필드 우선순위.
# EN에는 features의 번역본이 없으므로(products.json 실측 — features_en 키 없음)
# 실제로 존재하는 영문 실측 필드(hooks_en.thread / differentiators_en)로 대체한다.
APP_EXAMPLE_FIELD_PRIORITY = {
    "ko": ["features", "hooks_ko.thread"],
    "en": ["hooks_en.thread", "differentiators_en", "hooks_en.short"],
}


def _get_path(node, dotted):
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def pick_app_example_text(variant: dict, products_data: dict, product: dict, lang: str) -> str:
    """카피의 evidence가 가리키는 실제 값 중, "사용자가 사이트에서 실제로 하는 일"에
    해당하는 필드를 우선으로 골라 그대로 반환한다(문구 재작성 없음 — 발명 금지).
    evidence가 그 우선순위 필드를 가리키지 않으면, 그 프로그램의 우선순위 필드
    0번째로 폴백한다."""
    evidence = variant.get("evidence") or []
    priority = APP_EXAMPLE_FIELD_PRIORITY[lang]

    for e in evidence:
        val = resolve_evidence_path(products_data, e)
        if isinstance(val, str) and val.strip():
            for key in priority:
                if key in e:
                    return val.strip()

    for key in priority:
        node = _get_path(product, key)
        if isinstance(node, list) and node:
            first = node[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
    return None


_PRICE_NUM_RE = re.compile(r"₩\s?[\d][\d,]*|\$\s?[\d][\d,.]*|[\d][\d,]*\s?원|[\d][\d,]*\s?%")


def pick_price_stat(product: dict, lang: str):
    """products.json의 price_ko(유일한 가격 실측 필드)에서 숫자 토큰을 뽑아 큰 통계
    숫자로 쓰고, 캡션·내레이션에는 그 숫자가 담지 못하는 서로 다른 사실을 하나씩
    배정한다.

    (2026-09-01 시각 프레임 검수 결함 FIX — Defect 2) 예전엔 큰 숫자(예: ₩2,800)
    밑 캡션도 price_ko 문장을 그대로("종량제 ₩2,800 / 호출 (가장 저렴)") 써서 같은
    숫자를 캡션에서 또 반복했고, 번인 자막까지 그 캡션 전체를 다시 반복해 4초짜리
    한 세그먼트 안에서 "₩2,800"이라는 한 가지 사실이 숫자·캡션·자막 세 번 나왔다
    (t=12.0s 실측). 고쳐서: 숫자는 큰 통계 숫자 한 번만 쓰고, 캡션은 "이 가격에
    실제로 얻는 것"(기능 실측 문장 — features[1]. features[0]은 app_example
    세그먼트가 이미 쓰므로 같은 영상 안에서 또 반복하지 않도록 피한다)을 쓰고,
    내레이션(그리고 그걸 그대로 옮기는 번인 자막)은 price_ko에서 숫자 토큰만 지운
    "가격 구조" 설명("종량제 / 호출 (가장 저렴)")을 써서 숫자·캡션·자막이 서로
    다른 사실을 하나씩만 전달하게 했다 — 숫자를 캡션·자막 어디에도 다시 쓰지
    않는다.

    EN에는 price_ko/features 번역이 없다(products.json 실측 — price_en·features_en
    키 없음. evolve.py가 만든 EN seed variant들도 evidence에 "no EN price field,
    KRW figure carried over"라고 스스로 밝히는 것과 같은 관례). 그래서 EN 캡션은
    실제 URL로 대체하고(지어낸 영문 가격 문구를 새로 만들지 않는다), 내레이션에는
    캡션(URL)과 겹치지 않는 실측 EN 차별점(differentiators_en)을 배정한다."""
    price_ko = (product.get("price_ko") or "").strip()
    m = _PRICE_NUM_RE.search(price_ko)
    if m:
        number = m.group(0).strip()
    elif "무료" in price_ko:
        number = "무료" if lang == "ko" else "Free"
    elif price_ko:
        number = price_ko[:14]
    else:
        number = "?"

    # 가격 문장에서 숫자 토큰만 지운 "가격 구조" 설명 — 큰 숫자·캡션 어느 쪽과도
    # 겹치지 않는 별개 사실(예: "종량제 ₩2,800 / 호출 (가장 저렴)" -> "종량제 / 호출
    # (가장 저렴)").
    price_desc_no_number = _PRICE_NUM_RE.sub("", price_ko)
    price_desc_no_number = re.sub(r"\s+", " ", price_desc_no_number).strip(" /·-")

    features = product.get("features") or []
    benefit = None
    if len(features) > 1 and isinstance(features[1], str) and features[1].strip():
        benefit = features[1].strip()
    elif features and isinstance(features[0], str) and features[0].strip():
        benefit = features[0].strip()

    if lang == "ko":
        caption = benefit or "(가격 정보 없음)"
        # (실측 결함 2026-09-01) 여기서 price_desc_no_number 를 그대로 내레이션으로
        # 쓰면 "종량제 / 호출 (가장 저렴)" 이 된다. 화면 자막으로는 읽히지만 이 문자열은
        # TTS 로도 발화되므로 "종량제 슬래시 호출 가장 저렴" 이라는 비문이 들린다.
        # 문장에서 숫자만 기계적으로 지우면 문장이 아니라 파편이 남는다는 것이 요점이다.
        # price_ko 의 "종량제"(쓴 만큼 낸다) 라는 사실을 온전한 한 문장으로 다시 쓴다.
        # 숫자는 큰 글씨가 이미 보여 주므로 문장에서는 뺀다.
        if "종량제" in price_ko:
            narration = "호출한 만큼만 내는 종량제입니다."
        else:
            narration = price_desc_no_number or (benefit or "")
    else:
        # (실측 결함 2026-09-01) 캡션이 URL 이었다. 큰 숫자 아래 자리는 "이 값을 내면
        # 무엇을 얻는가"를 말하는 자리인데 URL 은 그 답이 아니고, 주소와 QR 은 마지막
        # 화면에 이미 크게 나온다. 실측 EN 차별점 중 앞의 두 개는 다른 세그먼트가 쓰므로
        # 세 번째([2])를 쓴다 — 같은 영상 안에서 같은 사실이 두 번 나오지 않는다.
        diffs_en = [d.strip() for d in (product.get("differentiators_en") or [])
                    if isinstance(d, str) and d.strip()]
        caption = diffs_en[2] if len(diffs_en) > 2 else (product.get("url") or "ideainnov.com")
        narration = diffs_en[0] if diffs_en else ""

    return number, caption, narration, price_ko


def _shorten(text: str, max_chars: int) -> str:
    """내레이션 전용 축약(화면 텍스트는 그대로 두고 이 문자열만 줄인다).
    어절 경계에서 자르고, 잘렸으면 말줄임표를 붙인다(단어 중간 절단 방지)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    cut = cut.rstrip(",.;:·-")
    return cut + "…"


def _dedupe_subtitle(narration_text: str, *onscreen_texts: str) -> str:
    """번인 자막(subtitle)에 쓸 문자열을 정한다.

    (2026-09-01 시각 프레임 검수 결함 FIX — Defect 1) t=1.5s 프레임 실측: 헤드라인이
    화면에 크게 떠 있는 동시에 번인 자막이 그 헤드라인을 글자 그대로 반복하고
    있었다(모든 세그먼트에서 같은 패턴). 자막은 "그 순간 실제로 말해지는 내레이션
    문장"이어야지 화면 그래픽 문구를 베낀 것이어서는 안 된다. 이 세그먼트의
    내레이션이 그 세그먼트의 주요 화면 문구(들)과 글자 그대로 같다면 — 즉 음성이
    화면에 없는 새 정보를 전혀 담지 않는다면 — 자막을 아예 띄우지 않는다. 이미
    다 보이는 문구를 하단에 또 태우는 건 정보 손실 없이 생략 가능하고(음소거 시청자는
    이미 화면에서 그 문구를 읽는다) 세이프존 하단 대역만 낭비한다(render_brand_end가
    이미 같은 이유로 자막을 생략하는 것과 동일한 원칙)."""
    n = (narration_text or "").strip()
    if not n:
        return ""
    for onscreen in onscreen_texts:
        if n == (onscreen or "").strip():
            return ""
    return n


def burn_safe(text: str) -> str:
    """ffmpeg drawtext(번인 자막)에 들어갈 문자열에서 ASCII '%'를 전각(％, U+FF05)
    으로 치환한다. 이 PC의 ffmpeg(n8.1)는 drawtext textfile에 ASCII '%'가 있으면
    "Stray %" 경고를 내고 그 drawtext 인스턴스 전체를 조용히 스킵한다(전체 명령은
    returncode 0으로 "성공"하므로 콘솔에 결함이 드러나지 않는다 — 가상인구페르소나
    릴스에서 프레임 픽셀 검증으로만 실측된 결함). 화면상의 실제 텍스트는 PIL로
    직접 프레임에 그려 넣으므로(ffmpeg drawtext 경로를 타지 않음) 이 치환이
    필요 없고, 여기서 건드리지 않는다 — 오직 burn_subtitles로 넘어가는 문자열에만
    적용한다."""
    return (text or "").replace("%", "％")


# ==============================================================================
# 신규 렌더러: render_brand_end — mograph 프리미티브만 사용(가상인구페르소나
# 릴스의 render_brand_end와 동일한 레이아웃 정신을 그대로 따르되, 사이즈 목표는
# 이번 작업 사양이 명시한 값(URL≈74px, 회사명≈72px 옐로우, QR≈405px)에 맞춘다).
# ==============================================================================
def render_brand_end(spec: dict, out_mp4, seconds: float) -> Path:
    """브랜드 엔드 카드 — 절대 페이드아웃하지 않는다(릴스 마지막 화면).

    세로 배치(위->아래, 세이프존 안, 겹침 없음):
        1) "IDEAINNOV.COM" 워드마크 — ease_out_back 팝인 (목표 ≈74px, 안 들어가면 자동 축소)
        2) 회사명(언어별) — 옐로우, 페이드인 (목표 ≈72px)
        3) QR 카드(≈405px 폭) — 페이드인, verify_scannable로 사전 검증된 PNG
        4) 하단 AI 생성 고지 문구 — 페이드인, 세이프존 맨 아래 고정

    (설계 메모, 가상인구페르소나 릴스와 동일한 이유) 이 세그먼트엔 번인 자막을
    넣지 않는다 — burn_subtitles가 자막을 세이프존 맨 아래에 고정 배치하는데,
    이 카드의 하단 고지 문구도 같은 자리를 써야 해서 서로 겹친다. 화면에 이미
    URL/회사명/QR로 필요한 정보가 다 드러나 있어 자막 없이도 정보 손실이 없다.
    """
    lang = spec["lang"]
    qr_png_path = spec["qr_png_path"]
    cta_text = spec.get("cta") or ""

    url_text = "IDEAINNOV.COM"
    company_text = "(주)미래사회알앤디" if lang == "ko" else "MIRAE SOCIETY R&D Inc."
    if lang == "ko":
        disclosure_text = ("AI가 생성·최적화한 홍보 카피 예시 · 수치 출처: "
                            "ideainnov.com 실측(common/products.json)")
    else:
        disclosure_text = ("AI-generated and optimized ad-copy example · figures sourced "
                            "from ideainnov.com (common/products.json)")

    tmp = Image.new("RGBA", (10, 10))
    td = ImageDraw.Draw(tmp)

    # --- 1) URL 워드마크: 목표 74px에서 시작해, 세이프존 92% 폭을 넘으면만 축소한다.
    max_url_w = int(mograph.SAFE_W * 0.92)
    url_size = 74
    url_font = mograph.get_font(True, url_size)
    while url_size > 30 and td.textlength(url_text, font=url_font) > max_url_w:
        url_size -= 2
        url_font = mograph.get_font(True, url_size)

    w_idea = td.textlength("IDEA", font=url_font)
    w_innov = td.textlength("INNOV", font=url_font)
    w_com = td.textlength(".COM", font=url_font)
    url_bbox = td.textbbox((0, 0), url_text, font=url_font)
    url_w = int(w_idea + w_innov + w_com) + 10
    url_h = (url_bbox[3] - url_bbox[1]) + 20
    url_layer = Image.new("RGBA", (url_w, url_h), (0, 0, 0, 0))
    ud = ImageDraw.Draw(url_layer)
    x = 5.0
    top = 10 - url_bbox[1]
    ud.text((x, top), "IDEA", font=url_font, fill=(255, 255, 255, 255))
    x += w_idea
    ud.text((x, top), "INNOV", font=url_font, fill=(*mograph.ACCENT, 255))
    x += w_innov
    ud.text((x, top), ".COM", font=url_font, fill=(255, 255, 255, 255))
    log(f"brand_end URL 폰트 크기={url_size}px, 실측 폭={url_w}px (세이프존 92%={max_url_w}px)")

    # --- 2) 회사명: 목표 72px, 세이프존 96% 폭을 넘으면만 축소한다. 옐로우. ---
    max_name_w = int(mograph.SAFE_W * 0.96)
    name_size = 72
    name_font = mograph.get_font(True, name_size)
    while name_size > 26 and td.textlength(company_text, font=name_font) > max_name_w:
        name_size -= 2
        name_font = mograph.get_font(True, name_size)
    name_bbox = td.textbbox((0, 0), company_text, font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_h = int(name_size * 1.32)

    # --- 3) QR 카드: 검증필 PNG를 목표 폭 405px로 스케일(원본 파일 수정 없음, 읽기만) ---
    qr_src = Image.open(qr_png_path).convert("RGBA")
    qr_w = 405
    qr_h = max(1, int(round(qr_src.height * (qr_w / qr_src.width))))
    qr_img = qr_src.resize((qr_w, qr_h), Image.LANCZOS)

    # --- 4) CTA(선택) + 하단 고지 문구: SUB 연회색, 세이프존 맨 아래 고정 ---
    cta_font = mograph.get_font(True, 34) if cta_text else None
    disc_font = mograph.get_font(False, 28)
    disc_max_w = int(mograph.SAFE_W * 0.94)
    disc_lines = mograph.wrap_text(td, disclosure_text, disc_font, disc_max_w)
    disc_lh = int(28 * 1.30)
    disc_h = disc_lh * len(disc_lines)
    cta_h = int(34 * 1.30) + 18 if cta_text else 0

    # --- 세로 배치: 고지문을 세이프존 맨 아래 고정, CTA는 그 바로 위, URL/회사명/QR
    # 묶음은 남은 공간에서 수직 중앙 정렬(요구사항: 세이프존 안, 겹치지 않게). ---
    gap_url_name = 40
    gap_name_qr = 34
    gap_qr_cta = 30
    gap_before_disc = 30

    disc_bottom = mograph.SAFE_BOTTOM - 14
    disc_top = disc_bottom - disc_h
    cta_top = disc_top - gap_before_disc - cta_h if cta_text else disc_top - gap_before_disc
    block_h = url_h + gap_url_name + name_h + gap_name_qr + qr_h
    avail_bottom = cta_top - gap_qr_cta if cta_text else disc_top - gap_before_disc
    avail_h = max(0, avail_bottom - mograph.SAFE_TOP)
    block_top = mograph.SAFE_TOP + max(0.0, (avail_h - block_h) / 2.0)

    url_y = block_top
    url_cx = mograph.CANVAS_W / 2.0
    url_cy = url_y + url_h / 2.0

    name_y = url_y + url_h + gap_url_name
    name_x = (mograph.CANVAS_W - name_w) / 2.0 - name_bbox[0]

    qr_y = name_y + name_h + gap_name_qr
    qr_x = (mograph.CANVAS_W - qr_w) / 2.0

    log(f"brand_end 레이아웃: url_y={url_y:.0f} h={url_h} / name_y={name_y:.0f} h={name_h} "
        f"/ qr_y={qr_y:.0f} h={qr_h} / cta_top={cta_top:.0f} / disc_top={disc_top:.0f} "
        f"h={disc_h} / SAFE=[{mograph.SAFE_TOP},{mograph.SAFE_BOTTOM}]")

    URL_POP_DUR = 0.5
    NAME_FADE_START, NAME_FADE_DUR = 0.5, 0.5
    QR_FADE_START, QR_FADE_DUR = 0.9, 0.5
    CTA_FADE_START, CTA_FADE_DUR = 0.2, 0.5
    DISC_FADE_START, DISC_FADE_DUR = 0.3, 0.5

    def draw_frame(i, n, t, seconds):
        frame = mograph.new_rgba_frame(t, seconds)
        layer = mograph.new_layer()
        ld = ImageDraw.Draw(layer)

        up = mograph.clamp01(t / URL_POP_DUR)
        uscale = max(0.0, mograph.ease_out_back(up))
        if uscale > 0.01:
            sw = max(1, int(url_w * uscale))
            sh = max(1, int(url_h * uscale))
            scaled = url_layer.resize((sw, sh), Image.LANCZOS)
            layer.alpha_composite(scaled, (int(url_cx - sw / 2), int(url_cy - sh / 2)))

        namep = mograph.clamp01((t - NAME_FADE_START) / NAME_FADE_DUR)
        if namep > 0:
            ne = mograph.ease_out_cubic(namep)
            alpha = int(255 * ne)
            ny = name_y + (1 - ne) * 18
            ld.text((name_x, ny), company_text, font=name_font,
                     fill=(mograph.ACCENT[0], mograph.ACCENT[1], mograph.ACCENT[2], alpha))

        if cta_text:
            ctap = mograph.clamp01((t - CTA_FADE_START) / CTA_FADE_DUR)
            if ctap > 0:
                ce = mograph.ease_out_cubic(ctap)
                calpha = int(255 * ce)
                cw = td.textlength(cta_text, font=cta_font)
                cx = (mograph.CANVAS_W - cw) / 2.0
                ld.text((cx, cta_top), cta_text, font=cta_font,
                        fill=(255, 255, 255, calpha))

        discp = mograph.clamp01((t - DISC_FADE_START) / DISC_FADE_DUR)
        if discp > 0:
            de = mograph.ease_out_cubic(discp)
            dalpha = int(255 * de)
            mograph.draw_lines_centered(
                ld, disc_lines, disc_font, disc_top,
                (mograph.SUB[0], mograph.SUB[1], mograph.SUB[2], dalpha), disc_lh,
            )

        frame.alpha_composite(layer)

        qp = mograph.clamp01((t - QR_FADE_START) / QR_FADE_DUR)
        if qp > 0:
            qe = mograph.ease_out_cubic(qp)
            if qe < 0.999:
                q = qr_img.copy()
                a_ch = q.getchannel("A").point(lambda a, s=qe: int(a * s))
                q.putalpha(a_ch)
            else:
                q = qr_img
            frame.alpha_composite(q, (int(qr_x), int(qr_y)))

        return frame.convert("RGB")

    return mograph.render_to_video(draw_frame, seconds, out_mp4)


# ==============================================================================
# 신규 렌더러 지원: "실제 이 사이트에서 하는 일" 브라우저 목업 PNG
# (가상인구페르소나 릴스의 build_terminal_png와 같은 정신 — 실측 텍스트만 그린다)
# ==============================================================================
def build_app_example_png(out_path: Path, product: dict, lang: str, example_text: str) -> Path:
    """products.json에서 가져온 실제 URL/프로그램명/기능 설명 문장을 브라우저
    목업 창 안에 그린다. 문장은 요약·재작성하지 않고 원문 그대로 넣는다(발명 금지).

    (실측 결함 수정) 처음엔 캔버스 높이를 1320px로 고정했는데, 실제 텍스트 콘텐츠는
    보통 400px 안에서 끝나 아래 900px 가까이가 빈 여백으로 남았다. render_screen_showcase
    가 이 이미지를 Ken Burns 줌인(kb="zoom_in")으로 보여주는데, 줌이 진행되며 이미지
    중심 기준으로 바깥쪽(특히 아래쪽 먼 여백에 있던 하단 고지 문구)이 크롭되어
    잘려나가는 게 검증 프레임(t=6.0s)에서 실측으로 확인됐다. 고지 문구를 이미지
    바닥에 고정하는 대신 실제 콘텐츠 바로 아래에 붙이고, 캔버스 높이 자체도 그
    콘텐츠 높이에 맞춰 동적으로 정하면 줌 크롭 안에 항상 들어온다.
    """
    W_IMG = 1040
    BG = (246, 247, 250)
    BAR = mograph.BG_TOP

    # 실제 그리기 전에 필요한 높이부터 계산한다(넉넉한 임시 캔버스에 텍스트 측정용
    # ImageDraw만 만들어 폰트 실측 폭/줄바꿈 결과를 얻는다).
    tmp = Image.new("RGB", (W_IMG, 10), BG)
    d0 = ImageDraw.Draw(tmp)

    bar_h = 96
    name_key = "name_ko" if lang == "ko" else "name_en"
    name_text = product.get(name_key) or product.get("name_ko") or product.get("key", "")
    name_font = mograph.get_font(True, 46)
    name_lines = mograph.wrap_text(d0, name_text, name_font, W_IMG - 120)

    badge_text = "실제 사용 예시" if lang == "ko" else "How it works"
    badge_font = mograph.get_font(True, 30)

    step_font = mograph.get_font(False, 36)
    step_lh = int(36 * 1.42)
    max_text_w = W_IMG - 160
    step_lines = mograph.wrap_text(d0, example_text, step_font, max_text_w)

    footer_font = mograph.get_font(False, 26)
    footer = ("출처: common/products.json (ideainnov.com 실측)" if lang == "ko"
              else "Source: common/products.json (ideainnov.com, live-measured)")

    ny = bar_h + 56 + int(46 * 1.28) * len(name_lines)
    y = ny + 46 + 46 + 34 + step_lh * len(step_lines)
    footer_y = y + 40
    H_IMG = footer_y + int(26 * 1.3) + 40

    img = Image.new("RGB", (W_IMG, H_IMG), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W_IMG, bar_h], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 52 + i * 34
        d.ellipse([cx - 9, bar_h // 2 - 9, cx + 9, bar_h // 2 + 9], fill=c)

    addr_font = mograph.get_font(False, 28)
    addr_text = product.get("url", "https://ideainnov.com")
    ax0, ax1 = 176, W_IMG - 48
    d.rounded_rectangle([ax0, 22, ax1, bar_h - 22], radius=(bar_h - 44) // 2, fill=(40, 44, 54))
    d.text((ax0 + 24, 22 + (bar_h - 44 - 34) / 2), addr_text, font=addr_font, fill=(206, 212, 224))

    ny = bar_h + 56
    for line in name_lines:
        d.text((60, ny), line, font=name_font, fill=BAR)
        ny += int(46 * 1.28)

    y = ny + 46
    bw = d.textlength(badge_text, font=badge_font)
    d.rounded_rectangle([60, y, 60 + bw + 32, y + 46], radius=23, fill=(255, 233, 176))
    d.text((76, y + 8), badge_text, font=badge_font, fill=(150, 100, 0))
    y += 46 + 34

    for line in step_lines:
        d.text((60, y), line, font=step_font, fill=(30, 34, 44))
        y += step_lh

    fw = d.textlength(footer, font=footer_font)
    d.text(((W_IMG - fw) / 2, footer_y), footer, font=footer_font, fill=(140, 148, 162))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


# ==============================================================================
# QR 오버레이(가상인구페르소나 릴스 overlay_qr_first_screen과 동일한 필터 패턴을
# 미러링 — 그 파일도 완성릴스/add_qr_overlay.py의 필터를 "복사"만 한 것이었다)
# ==============================================================================
QR_X, QR_Y = 642, 1268           # 세이프존 안, 우하단(가상인구페르소나 릴스와 동일 배치)
QR_OVERLAY_WIDTH = 220           # 하단 번인 자막과 겹치지 않도록 축소한 폭(동일 사유)
QR_OVERLAY_START = 0.40
QR_OVERLAY_END = 3.20
QR_OVERLAY_FADE_IN = 0.25
QR_OVERLAY_FADE_OUT_DUR = 0.30
QR_OVERLAY_FADE_OUT_START = QR_OVERLAY_END - QR_OVERLAY_FADE_OUT_DUR


def overlay_qr_first_screen(src: Path, dst: Path, qr_png: Path,
                             start: float, fade_out_start: float, end: float,
                             fade_in: float = 0.25):
    fin = fade_in
    fout = max(0.05, end - fade_out_start)
    filt = (
        f"[1:v]scale={QR_OVERLAY_WIDTH}:-2,format=rgba,fade=in:st={start:.3f}:d={fin:.3f}:alpha=1,"
        f"fade=out:st={fade_out_start:.3f}:d={fout:.3f}:alpha=1[qr];"
        f"[0:v][qr]overlay={QR_X}:{QR_Y}:enable='between(t,{start:.3f},{end:.3f})'[v]"
    )

    def build_cmd(gpu_ok):
        return [bps.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(src), "-loop", "1", "-i", str(qr_png),
                "-filter_complex", filt, "-map", "[v]", "-map", "0:a?",
                *bps.video_encode_args(quality=19, gpu_ok=gpu_ok)[0],
                "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(dst)]

    bps.run_encode(build_cmd, "QR 오버레이(첫 화면)")
    return dst


def ensure_qr_png() -> Path:
    """QR PNG가 있으면(가상인구페르소나 릴스와 동일 경로) 그대로 재사용하고,
    없으면 common/qr_card.py로 이 스크립트 작업폴더(WORK) 안에 새로 만든다
    (홍보문구최적화/ 밖에는 아무 것도 쓰지 않는다). 생성 직후 반드시
    verify_scannable로 되읽기 검증한다(qr_card.py 자체 권고 사용법)."""
    if QR_PNG_DEFAULT.exists():
        log(f"QR PNG 재사용: {QR_PNG_DEFAULT}")
        return QR_PNG_DEFAULT

    fallback_path = WORK / "qr_ideainnov_fallback.png"
    log(f"[WARN] 기본 QR PNG 없음({QR_PNG_DEFAULT}) -> qr_card.py로 새로 생성: {fallback_path}")
    result = save_qr_card(QR_URL, fallback_path, caption="IDEAINNOV.COM")
    ok_full = result["verify"].get("x1.0", (False, ""))[0]
    if not ok_full:
        raise SystemExit(f"[FAIL] 새로 생성한 QR이 되읽기 검증에 실패했습니다: {result['verify']}")
    log(f"QR 생성+검증 완료: {result['verify']}")
    return fallback_path


# ==============================================================================
# 세그먼트 정의 — 정확히 3.5+5.0+4.0+5.0+4.5 = 22.0초.
# ==============================================================================
def build_segments(variant: dict, products_data: dict, product: dict, lang: str,
                    app_png: Path, qr_png: Path):
    headline = variant["headline"].strip()
    body = variant["body"].strip()
    cta = variant["cta"].strip()

    example_text = pick_app_example_text(variant, products_data, product, lang)
    if not example_text:
        raise SystemExit(
            f"[FAIL] products.json에서 '실제 사용 예시'로 쓸 수 있는 sourced 문장을 "
            f"찾지 못했습니다(program={variant['products_program']}, lang={lang}). "
            f"발명 금지 원칙상 지어낼 수 없어 중단합니다."
        )
    example_caption = _shorten(example_text, 70)

    stat_number, stat_caption, stat_narration_raw, price_ko_raw = pick_price_stat(product, lang)

    pain_key = "pain_ko" if lang == "ko" else "pain_en"
    pain_text = (product.get(pain_key) or "").strip()
    before_label = "BEFORE"
    after_label = "AFTER"
    before_body = pain_text if pain_text else ("(products.json에 pain 필드 없음)" if lang == "ko"
                                                else "(no pain field in products.json)")
    after_body = body

    # 세그먼트별 내레이션(=실제로 말해지는 문장) 먼저 정하고, 번인 자막은 그
    # 내레이션에서만 가져온다(2026-09-01 결함 FIX — Defect 1). _dedupe_subtitle이
    # 내레이션이 그 세그먼트의 주요 화면 문구와 글자 그대로 같으면(=화면에 없는 새
    # 정보가 없으면) 자막을 생략한다.
    #
    # 축약 상한(60/80/60자)은 언어 중립적으로 넉넉히 잡았다 — KO 짧은 헤드라인
    # (17자)·짧은 기능문(28자)·짧은 가격구조문(14자)은 이 상한보다 훨씬 짧아 전혀
    # 잘리지 않고(기존 20/28/30자 상한과 결과 동일, 회귀 없음, 실측 확인됨), 그래서
    # 화면 문구와 글자 그대로 같아져 자막이 생략된다. EN은 같은 정보를 담는 데
    # 한국어보다 글자 수가 훨씬 더 필요하다(예: "Equations stay editable objects,
    # never flattened into images"=63자) — 예전 20/28자 상한을 그대로 썼다면 EN
    # 헤드라인·기능문이 "Don't let your…"처럼 단어 중간에서 끊긴 채 번인 자막으로
    # 노출됐을 것이다(자막이 화면 문구를 그대로 복제하진 않지만 읽을 수 없는 조각을
    # 보여주는 것도 defect 1이 막으려는 것과 같은 문제 — 소리 없이 보는 시청자가
    # 따라갈 수 있는 온전한 문장이어야 한다). 넉넉한 상한 덕에 EN 헤드라인·기능문도
    # 전체 문장이 내레이션이 되어 화면 문구와 같아지고, 그래서 자막이 똑같이
    # 생략된다 — KO/EN 두 언어가 같은 이유로 같은 결과(자막 생략)를 내는 "짝"이
    # 된다(장군님 요청: 두 언어 영상이 서로 무관해 보이지 않게).
    hook_narration = _shorten(headline, 60)
    app_example_narration = _shorten(example_text, 80)
    reveal_narration = _shorten(cta, 20)
    # stat 내레이션은 "가격 구조" 설명(KO 예: "종량제 / 호출 (가장 저렴)", EN 예:
    # differentiators_en[0]) — 큰 숫자·캡션(=이 가격에 얻는 기능) 어느 쪽과도
    # 겹치지 않는 세 번째 사실이다.
    # (실측 결함 2026-09-01) 상한 60자가 EN 실측 문장 71자를 "nothing to..." 로
    # 문장 중간에서 잘랐다. 말끝이 잘린 자막은 없는 자막보다 나쁘다. 번인 자막은
    # 2줄까지 자연스럽게 감싸므로 상한을 문장이 들어갈 만큼 올린다.
    stat_narration = _shorten(stat_narration_raw, 90)

    return [
        dict(
            name="hook", motion="kinetic_title", seconds=3.5,
            spec={"text": headline},
            subtitle=_dedupe_subtitle(hook_narration, headline),
            narration=hook_narration,
        ),
        dict(
            name="app_example", motion="screen_showcase", seconds=5.0,
            spec={"image": str(app_png), "caption": example_caption, "kb": "zoom_in"},
            subtitle=_dedupe_subtitle(app_example_narration, example_text, example_caption),
            narration=app_example_narration,
        ),
        dict(
            name="stat", motion="stat_pop", seconds=4.0,
            spec={"number": stat_number, "caption": stat_caption},
            # (2026-09-01 결함 FIX — Defect 2) 예전엔 자막이 "{숫자} — {캡션}"으로
            # 큰 숫자와 캡션을 그대로 다시 이어붙여, 4초 세그먼트 안에서 같은 가격
            # 사실이 숫자·캡션·자막 세 번 나왔다(t=12.0s 실측). 이제 자막은 stat_
            # narration(가격 구조 설명)만 옮긴다 — 숫자·캡션 어디에도 없는 세 번째
            # 사실이라 _dedupe_subtitle을 통과해 그대로 뜬다.
            subtitle=_dedupe_subtitle(stat_narration, stat_number, stat_caption),
            narration=stat_narration,
        ),
        dict(
            name="reveal", motion="before_after", seconds=5.0,
            spec={
                "before_label": before_label, "before_body": before_body,
                "after_label": after_label, "after_body": after_body,
            },
            # body 전체를 다시 읽으면(특히 body가 app_example과 같은 evidence를 쓴
            # 경우) 위 app_example 내레이션과 내용이 겹쳐 스크립트만 길어진다. 화면엔
            # before/after 문구가 이미 다 보이므로, 내레이션은 CTA만 짧게 읽는다.
            # CTA는 이 세그먼트 화면(before/after 문구)에는 나오지 않으므로
            # _dedupe_subtitle을 통과해 그대로 뜬다.
            subtitle=_dedupe_subtitle(reveal_narration, before_body, after_body),
            narration=reveal_narration,
        ),
        dict(
            name="brand_end", motion="brand_end", seconds=4.5,
            spec={"lang": lang, "qr_png_path": str(qr_png), "cta": cta},
            subtitle="",  # 하단 고지 문구와 겹치므로 번인 자막 없음(render_brand_end 사유 참고)
            narration=(f"{_shorten(cta, 10)}. 아이디어이노브 닷컴, 미래사회알앤디." if lang == "ko"
                       else f"{_shorten(cta, 16)}. IDEAINNOV.COM, MIRAE SOCIETY R&D."),
        ),
    ]


RENDER_FUNCS = {
    "kinetic_title": mograph.render_kinetic_title,
    "screen_showcase": mograph.render_screen_showcase,
    "stat_pop": mograph.render_stat_pop,
    "before_after": mograph.render_before_after,
    "brand_end": render_brand_end,
}


# ==============================================================================
# 빌드
# ==============================================================================
def build(variant: dict, products_data: dict, product: dict, lang: str, final_path: Path):
    seg_dir = WORK / f"seg_{lang}_{variant['id']}"
    seg_dir.mkdir(parents=True, exist_ok=True)

    app_png = seg_dir / "app_example.png"
    example_text_for_png = pick_app_example_text(variant, products_data, product, lang)
    build_app_example_png(app_png, product, lang, example_text_for_png)
    log(f"app_example PNG 생성: {app_png}")

    qr_png = ensure_qr_png()

    segments = build_segments(variant, products_data, product, lang, app_png, qr_png)

    parts = []
    seg_bounds = []
    t_cursor = 0.0
    for seg in segments:
        motion = seg["motion"]
        seconds = seg["seconds"]
        fn = RENDER_FUNCS[motion]
        h = bps._spec_hash({**seg["spec"], "_seconds": seconds, "_motion": motion})

        raw = seg_dir / f"{seg['name']}_{h}.mp4"
        if not raw.exists():
            fn(seg["spec"], raw, seconds)
        else:
            log(f"렌더 캐시 재사용: {raw.name}")

        normed = seg_dir / f"{seg['name']}_norm_{h}.mp4"
        if not normed.exists():
            bps.normalize(raw, normed, seconds=seconds)

        parts.append(normed)
        seg_bounds.append((t_cursor, t_cursor + seconds, seg["name"]))
        t_cursor += seconds

    log(f"세그먼트 합계 {t_cursor:.1f}초 (기대 22.0초)")
    assert abs(t_cursor - 22.0) < 1e-6, f"세그먼트 합이 22.0초가 아님: {t_cursor}"

    silent_concat = seg_dir / "concat.mp4"
    bps.concat(parts, silent_concat)
    vdur = bps.dur_of(silent_concat)
    log(f"무음 조립 완료: {vdur:.2f}초")

    voice_name = bps.VOICE_KO if lang == "ko" else bps.VOICE_EN
    raw_script = " ".join(seg["narration"].strip() for seg in segments if seg.get("narration", "").strip())
    script = " ".join(to_spoken_ko(s) for s in
                       [seg["narration"].strip() for seg in segments if seg.get("narration", "").strip()]) \
        if lang == "ko" else raw_script

    voice_start = 0.35
    script_h = hashlib.sha1(script.encode("utf-8")).hexdigest()[:10]
    mp3 = seg_dir / f"voice_full_{script_h}.mp3"
    budget = max(1.0, vdur - voice_start - 0.6)
    vlen = 0.0
    rate = 0
    if not mp3.exists():
        # 사양 상한: rate는 +0% -> +12%만 시도한다(그 이상은 허용되지 않음).
        for rate in (0, 12):
            bps.make_voice(script, voice_name, mp3, rate=f"+{rate}%")
            vlen = bps.dur_of(mp3)
            if vlen <= budget:
                break
        if vlen > budget:
            # 조용히 자르지 않는다: -shortest로 잘리면 마지막 CTA 문장이 통째로
            # 사라지는데 영상은 멀쩡해 보여서 검수를 통과해버린다(가상인구페르소나
            # 릴스에서 실측된 결함). rate 상한(+12%)까지 다 써도 예산을 넘으면
            # 여기서 하드 실패시켜 스크립트를 줄이도록 강제한다.
            mp3.unlink(missing_ok=True)
            raise SystemExit(
                f"[FAIL] 내레이션 {vlen:.2f}s > 예산 {budget:.2f}s (rate +12%까지 시도). "
                f"narration 필드들을 줄이십시오 — rate를 +12% 넘게 올리거나 -shortest로 "
                f"CTA를 조용히 자르는 대신 실패로 처리합니다. script={script!r}"
            )
    else:
        vlen = bps.dur_of(mp3)
    log(f"내레이션 {vlen:.2f}s (영상 {vdur:.2f}s, rate +{rate}%, lang={lang})")

    voiced = seg_dir / f"voiced_{script_h}.mp4"
    if not voiced.exists():
        bps.mix_voice(silent_concat, mp3, voiced)

    explicit_timings = []
    for start, end, name in seg_bounds:
        seg = next(s for s in segments if s["name"] == name)
        text = seg.get("subtitle", "").strip()
        if not text:
            continue
        t0 = start + 0.25
        t1 = max(t0 + 0.6, end - 0.25)
        explicit_timings.append((t0, t1, burn_safe(text)))
    sub_h = hashlib.sha1(repr(explicit_timings).encode("utf-8")).hexdigest()[:10]

    subbed = seg_dir / f"subbed_{script_h}_{sub_h}.mp4"
    if not subbed.exists():
        bps.burn_subtitles(mograph, voiced, None, voice_start=0.0, voice_len=0.0,
                            out_mp4=subbed, tag=f"copy{lang}", explicit_timings=explicit_timings)

    assembled = seg_dir / "assembled_noqr.mp4"
    bps.add_loop_tail(subbed, assembled)
    adur = bps.dur_of(assembled)
    log(f"루프 꼬리 포함 조립 완료: {adur:.2f}초 (QR 오버레이 전)")

    overlay_qr_first_screen(assembled, final_path, qr_png,
                             QR_OVERLAY_START, QR_OVERLAY_FADE_OUT_START, QR_OVERLAY_END,
                             fade_in=QR_OVERLAY_FADE_IN)
    fdur = bps.dur_of(final_path)
    log(f"[OK] {final_path.name} — {fdur:.2f}초")
    return final_path, fdur, seg_bounds


# ==============================================================================
# 검증
# ==============================================================================
def extract_frame(video, t, out_png):
    bps.run([bps.FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(video), "-ss", f"{t:.3f}", "-frames:v", "1", "-update", "1",
             str(out_png)], f"프레임 추출 t={t}")
    return out_png


def probe_video(path):
    p = bps.run_utf8([bps.FFPROBE, "-v", "error", "-select_streams", "v:0",
                       "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)])
    wh = (p.stdout or "").strip()
    w, h = (wh.split(",") + ["0", "0"])[:2]
    a = bps.run_utf8([bps.FFPROBE, "-v", "error", "-select_streams", "a",
                       "-show_entries", "stream=index", "-of", "csv=p=0", str(path)])
    has_audio = bool((a.stdout or "").strip())
    dur = bps.dur_of(path)
    return int(w or 0), int(h or 0), has_audio, dur


def decode_qr(png_path, expect_url):
    import cv2
    import numpy as np
    im = Image.open(png_path).convert("RGB")
    det = cv2.QRCodeDetector()
    w, h = im.size
    candidates = [("full", im)]
    candidates.append(("crop_overlay", im.crop((max(0, QR_X - 20), max(0, QR_Y - 20),
                                                 min(w, QR_X + 400), min(h, QR_Y + 440)))))
    candidates.append(("crop_center_lower", im.crop((int(w * 0.15), int(h * 0.35),
                                                       int(w * 0.85), int(h * 0.95)))))
    data = ""
    for tag, region in candidates:
        arr = np.array(region.convert("RGB"))[:, :, ::-1]
        try:
            data, pts, _ = det.detectAndDecode(arr)
        except cv2.error:
            data = ""
        if data == expect_url:
            return True, tag, data
    return False, "decode fail", data


def verify(final_path: Path, seg_bounds, lang: str):
    log("=== 검증 시작 ===")
    if not final_path.exists():
        return {"ok": False, "error": f"파일 없음: {final_path}"}

    w, h, has_audio, dur = probe_video(final_path)
    ok_dur = abs(dur - 22.0) <= 0.6
    ok_res = (w, h) == (bps.W, bps.H)
    log(f"[VERIFY] duration={dur:.2f}s (22.0±0.6? {ok_dur}) resolution={w}x{h} "
        f"(1080x1920? {ok_res}) audio={has_audio}")

    frame_times = [0.02, 1.5, 6.0, 10.5, 15.0, 19.75, 21.0]
    frame_paths = {}
    for t in frame_times:
        out_png = VERIFY_DIR / f"{lang}_t{t:.2f}s.png"
        extract_frame(final_path, t, out_png)
        frame_paths[t] = out_png
        log(f"  프레임 추출: t={t:.2f}s -> {out_png}")

    ok_qr_absent_t0, tag0, data0 = decode_qr(frame_paths[0.02], QR_URL)
    ok_qr_overlay, tag1, data1 = decode_qr(frame_paths[1.5], QR_URL)
    ok_qr_brand, tag2, data2 = decode_qr(frame_paths[21.0], QR_URL)

    log(f"[VERIFY] QR@0.02s 부재 기대: decode={ok_qr_absent_t0} (False가 정상) tag={tag0} data={data0!r}")
    log(f"[VERIFY] QR@1.5s(오버레이) decode={ok_qr_overlay} tag={tag1} data={data1!r}")
    log(f"[VERIFY] QR@21.0s(브랜드엔드) decode={ok_qr_brand} tag={tag2} data={data2!r}")

    result = {
        "ok": True,
        "duration": dur, "ok_duration": ok_dur,
        "resolution": (w, h), "ok_resolution": ok_res,
        "has_audio": has_audio,
        "frames": frame_paths,
        "qr_absent_t0": (not ok_qr_absent_t0, tag0, data0),
        "qr_1_5": (ok_qr_overlay, tag1, data1),
        "qr_21_0": (ok_qr_brand, tag2, data2),
    }

    all_pass = (ok_dur and ok_res and has_audio and (not ok_qr_absent_t0)
                and ok_qr_overlay and ok_qr_brand and len(frame_paths) >= 3)
    result["all_pass"] = all_pass

    print("\n=== 검증 요약 ===")
    print(f"  {'PASS' if all_pass else 'FAIL'}  전체")
    print(f"  {'PASS' if ok_dur else 'FAIL'}  duration={dur:.2f}s (기대 22.0±0.6)")
    print(f"  {'PASS' if ok_res else 'FAIL'}  resolution={w}x{h} (기대 1080x1920)")
    print(f"  {'PASS' if has_audio else 'FAIL'}  오디오 트랙 존재={has_audio}")
    print(f"  {'PASS' if (not ok_qr_absent_t0) else 'FAIL'}  QR t=0.02s 부재(decode={ok_qr_absent_t0})")
    print(f"  {'PASS' if ok_qr_overlay else 'FAIL'}  QR t=1.5s(오버레이) decode={ok_qr_overlay}")
    print(f"  {'PASS' if ok_qr_brand else 'FAIL'}  QR t=21.0s(브랜드엔드) decode={ok_qr_brand}")
    print(f"  프레임 {len(frame_paths)}장 -> {VERIFY_DIR}")

    return result


# ==============================================================================
# main
# ==============================================================================
def main():
    ap = argparse.ArgumentParser(description="홍보 카피 최적화 22초 릴스 빌더")
    ap.add_argument("--copy-json", required=True, help="winning_variant 또는 FINAL_REPORT.json 경로")
    ap.add_argument("--lang", required=True, choices=["ko", "en"])
    ap.add_argument("--out", default=None, help="출력 mp4 경로(생략 시 video/ 밑 기본 파일명)")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    copy_json_path = Path(args.copy_json).resolve()
    final_path = Path(args.out).resolve() if args.out else (OUT_DIR / DEFAULT_OUT_NAMES[args.lang])

    variant = load_variant(copy_json_path, args.lang)
    products_data = load_products()
    product = get_product(products_data, variant["products_program"])
    log(f"variant id={variant['id']!r} lang={variant['lang']} "
        f"products_program={variant['products_program']!r}")

    if args.verify_only:
        if not final_path.exists():
            sys.exit(f"[FAIL] {final_path} 없음 — 먼저 빌드하세요")
        segments = build_segments(variant, products_data, product, args.lang,
                                   app_png=WORK / "dummy_for_verify.png", qr_png=ensure_qr_png())
        seg_bounds = []
        t_cursor = 0.0
        for seg in segments:
            seg_bounds.append((t_cursor, t_cursor + seg["seconds"], seg["name"]))
            t_cursor += seg["seconds"]
        result = verify(final_path, seg_bounds, args.lang)
    else:
        final_path, fdur, seg_bounds = build(variant, products_data, product, args.lang, final_path)
        result = verify(final_path, seg_bounds, args.lang)

    print("\n=== 완성 ===")
    print(f"  {final_path}  ({result.get('duration', 0):.2f}s)")
    for start, end, name in seg_bounds:
        print(f"      - {name}: {start:.1f}s ~ {end:.1f}s")
    if not result.get("all_pass", False):
        sys.exit(1)


if __name__ == "__main__":
    main()
