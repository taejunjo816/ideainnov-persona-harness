# -*- coding: utf-8 -*-
"""
JSON Schemas for the batched ad-copy-verdict calls, passed to
`claude -p ... --json-schema '<...>'` so the CLI enforces structured output
itself (no fragile regex/markdown-fence JSON extraction needed).

This is the copy-optimization sibling of
`가상인구페르소나/ideainnov-persona-harness/harness/schemas.py`: same
batch-of-N-personas mechanism, but the judgment target is ONE piece of ad
copy (headline/body/cta) instead of a product spec, and there is no
round1/round2 "public opinion" broadcast — each variant is evaluated once
per persona batch (see harness/run_copy_harness.py).
"""

PERSONA_VERDICT_PROPERTIES = {
    "persona_id": {
        "type": "string",
        "description": "Echo back the persona_id given in the input, unchanged.",
    },
    "would_click": {
        "type": "string",
        "enum": ["yes", "maybe", "no"],
        "description": "Would this persona realistically stop scrolling and click/tap this ad copy?",
    },
    "hook_phrase": {
        "type": "string",
        "description": "The exact word/phrase FROM the given headline+body+cta that actually drew this "
                        "persona's attention. Must be a substring that literally appears in the copy. "
                        "Empty string \"\" if nothing drew them.",
    },
    "blocker": {
        "type": "string",
        "description": "One concrete sentence: the single biggest thing that stops/would stop this "
                        "persona from clicking. Empty string \"\" if there is no real blocker.",
    },
    "trust": {
        "type": "integer",
        "minimum": 1,
        "maximum": 5,
        "description": "1-5: how much this persona trusts the copy's claims at face value "
                        "(1 = sounds fake/overpromising, 5 = sounds credible and specific).",
    },
    "reasoning": {
        "type": "string",
        "description": "One concise sentence (~15-25 words) grounded in THIS persona's own "
                        "occupation/field/education/hobbies.",
    },
}

PERSONA_VERDICT_REQUIRED = list(PERSONA_VERDICT_PROPERTIES.keys())


def round_schema(batch_size: int) -> dict:
    """Wrap the per-persona verdict schema into the 'exactly one verdict per
    persona in the batch, same order' envelope `claude --json-schema` enforces.
    Named `round_schema` (not `batch_schema`) to mirror the sibling harness's
    round1_schema/round2_schema naming, even though this harness only ever
    runs a single evaluation round per (variant, persona-batch) pair — the
    output files are still named round_XX.json per the spec for this program.
    """
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "minItems": batch_size,
                "maxItems": batch_size,
                "items": {
                    "type": "object",
                    "properties": dict(PERSONA_VERDICT_PROPERTIES),
                    "required": list(PERSONA_VERDICT_REQUIRED),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }


def validate_verdicts(verdicts, want_persona_ids: set, batch_size: int) -> list[str]:
    """Local, defensive re-validation of a structured-output payload —
    applied identically to real `claude` CLI output AND to the --dry-run
    stub, so a malformed verdict (missing field, out-of-enum value,
    out-of-range trust, wrong count/ids) is caught and reported LOUDLY
    instead of silently flowing into aggregation/scoring.

    Returns a list of human-readable problem strings (empty list = valid).
    `claude --json-schema` already enforces this for real calls, but this
    function is the ONLY validation path for --dry-run output, and doubles
    as a second, independent check for real calls too.
    """
    problems: list[str] = []
    if not isinstance(verdicts, list):
        return [f"verdicts is not a list: {type(verdicts).__name__}"]
    if len(verdicts) != batch_size:
        problems.append(f"expected {batch_size} verdicts, got {len(verdicts)}")

    got_ids = []
    for i, v in enumerate(verdicts):
        if not isinstance(v, dict):
            problems.append(f"verdict[{i}] is not an object: {type(v).__name__}")
            continue
        missing = [k for k in PERSONA_VERDICT_REQUIRED if k not in v]
        if missing:
            problems.append(f"verdict[{i}] missing required field(s): {missing}")
            continue
        if v["would_click"] not in ("yes", "maybe", "no"):
            problems.append(f"verdict[{i}] would_click out of enum: {v['would_click']!r}")
        if not isinstance(v["trust"], int) or isinstance(v["trust"], bool) or not (1 <= v["trust"] <= 5):
            problems.append(f"verdict[{i}] trust out of range/type (want int 1-5): {v['trust']!r}")
        for k in ("persona_id", "hook_phrase", "blocker", "reasoning"):
            if not isinstance(v[k], str):
                problems.append(f"verdict[{i}] field '{k}' is not a string: {type(v[k]).__name__}")
        got_ids.append(v.get("persona_id"))

    got_id_set = set(got_ids)
    if got_id_set != want_persona_ids:
        problems.append(
            f"persona_id mismatch: missing={want_persona_ids - got_id_set} "
            f"extra={got_id_set - want_persona_ids}"
        )
    if len(got_ids) != len(got_id_set):
        dupes = [pid for pid in got_id_set if got_ids.count(pid) > 1]
        problems.append(f"duplicate persona_id(s) in verdicts: {dupes}")

    return problems
