# -*- coding: utf-8 -*-
"""
JSON Schemas for the batched persona-verdict calls, passed to
`claude -p ... --json-schema '<...>'` so the CLI enforces structured output
itself (no fragile regex/markdown-fence JSON extraction needed).

Both rounds share the same per-persona fields; round 2 adds two fields that
capture whether/why the "public opinion summary" shifted that persona's
verdict.
"""

BASE_ITEM_PROPERTIES = {
    "persona_id": {"type": "string", "description": "Echo back the persona_id given in the input, unchanged."},
    "would_use": {"type": "string", "enum": ["yes", "maybe", "no"]},
    "user_type": {
        "type": "string",
        "enum": ["core_target", "adjacent", "not_applicable"],
        "description": "core_target: this product is squarely built for someone like them. "
                        "adjacent: plausible occasional/curious use but not their core job. "
                        "not_applicable: irrelevant to their life or job.",
    },
    "would_pay": {"type": "string", "enum": ["yes", "no", "only_free_tier"]},
    "max_price_krw_month": {
        "type": ["integer", "null"],
        "description": "Their realistic monthly willingness-to-pay ceiling in KRW, or null if would_pay is 'no'.",
    },
    "top_objection": {
        "type": "string",
        "description": "Their single biggest, most specific objection or reason for disinterest (empty string if none).",
    },
    "reasoning": {
        "type": "string",
        "description": "One concise sentence (~20-30 words) grounded in THIS persona's own occupation/field/education/hobbies.",
    },
}

ROUND2_EXTRA_PROPERTIES = {
    "changed_from_round1": {
        "type": "boolean",
        "description": "true if would_use, user_type, or would_pay changed after seeing the public-opinion summary.",
    },
    "change_reason": {
        "type": ["string", "null"],
        "description": "If changed_from_round1 is true, one short phrase on why (e.g. social proof, reconsidered price). Otherwise null.",
    },
}


def round1_schema(batch_size: int) -> dict:
    """Exactly one verdict object per persona in the batch, same order."""
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "minItems": batch_size,
                "maxItems": batch_size,
                "items": {
                    "type": "object",
                    "properties": dict(BASE_ITEM_PROPERTIES),
                    "required": list(BASE_ITEM_PROPERTIES.keys()),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }


def round2_schema(batch_size: int) -> dict:
    props = dict(BASE_ITEM_PROPERTIES)
    props.update(ROUND2_EXTRA_PROPERTIES)
    return {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "minItems": batch_size,
                "maxItems": batch_size,
                "items": {
                    "type": "object",
                    "properties": props,
                    "required": list(props.keys()),
                    "additionalProperties": False,
                },
            }
        },
        "required": ["verdicts"],
        "additionalProperties": False,
    }
