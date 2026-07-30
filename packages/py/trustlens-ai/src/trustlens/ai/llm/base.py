"""Shared parsing and validation for LLM analysers.

Everything a model returns is treated as untrusted: values are coerced,
clamped and filtered against an allowlist before they reach the domain. An LLM
that hallucinates `risk_score: 5000` or invents a label must not be able to
distort a score.
"""

from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_LABELS = frozenset(
    {
        "urgency_pressure",
        "off_platform_contact",
        "advance_fee",
        "price_anomaly",
        "impersonation",
        "payment_outside_escrow",
        "stolen_goods",
        "low_detail",
        "prompt_injection_attempt",
    }
)

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def parse_analysis_json(raw_text: str) -> dict[str, Any]:
    """Extract and sanitise the model's JSON response."""
    match = _JSON_BLOCK.search(raw_text)
    if match is None:
        raise ValueError("model response contained no JSON object")

    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("model response was not a JSON object")

    risk = _clamp(_as_float(data.get("risk_score"), 50.0), 0.0, 100.0)
    confidence = _clamp(_as_float(data.get("confidence"), 0.5), 0.0, 1.0)

    labels = [
        label
        for label in data.get("labels", [])
        if isinstance(label, str) and label in ALLOWED_LABELS
    ]

    findings_raw = data.get("findings", {})
    findings = (
        {
            key: [str(item)[:400] for item in value][:5]
            for key, value in findings_raw.items()
            if key in ALLOWED_LABELS and isinstance(value, list)
        }
        if isinstance(findings_raw, dict)
        else {}
    )

    return {
        "risk_score": risk,
        "confidence": confidence,
        "labels": labels,
        "findings": findings,
        "summary": str(data.get("summary", ""))[:400],
    }


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


__all__ = ["ALLOWED_LABELS", "parse_analysis_json"]
