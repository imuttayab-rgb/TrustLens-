"""Feature extraction, shared between training (apps/ml) and inference.

ONE implementation, two callers. Train/serve feature skew is the classic
reason a classifier scores 0.94 offline and behaves randomly in production, so
apps/ml imports this module rather than reimplementing it.
"""

from __future__ import annotations

import re

URGENCY_TERMS = ("urgent", "today only", "hurry", "last chance", "first come", "asap")
CONTACT_TERMS = ("whatsapp", "telegram", "dm me", "contact me on", "call only")
PAYMENT_TERMS = ("advance", "deposit", "token money", "bank transfer", "crypto", "gift card")
SCARCITY_TERMS = ("only one left", "final price", "no bargaining", "must sell")


def extract_features(
    *, title: str, description: str, price: float | None, category: str | None
) -> dict[str, float]:
    """A small, explainable feature set.

    Deliberately interpretable: a feature that cannot be explained cannot be
    defended in an appeal, and this classifier feeds a scored signal.
    """
    text = f"{title} {description}".lower()
    words = re.findall(r"\w+", text)

    return {
        "char_length": float(len(text)),
        "word_count": float(len(words)),
        "unique_word_ratio": len(set(words)) / len(words) if words else 0.0,
        "uppercase_ratio": (
            sum(1 for c in f"{title}{description}" if c.isupper())
            / max(len(f"{title}{description}"), 1)
        ),
        "exclamation_count": float(text.count("!")),
        "urgency_hits": float(sum(term in text for term in URGENCY_TERMS)),
        "contact_hits": float(sum(term in text for term in CONTACT_TERMS)),
        "payment_hits": float(sum(term in text for term in PAYMENT_TERMS)),
        "scarcity_hits": float(sum(term in text for term in SCARCITY_TERMS)),
        "digit_ratio": sum(c.isdigit() for c in text) / max(len(text), 1),
        "has_price": 1.0 if price is not None else 0.0,
        "has_category": 1.0 if category else 0.0,
        "phone_in_text": 1.0 if re.search(r"\b\d{4}[- ]?\d{7}\b", text) else 0.0,
        "url_in_text": 1.0 if re.search(r"https?://|www\.", text) else 0.0,
    }


FEATURE_ORDER: tuple[str, ...] = tuple(
    extract_features(title="", description="", price=None, category=None).keys()
)


def to_vector(features: dict[str, float]) -> list[float]:
    """Fixed ordering - a reordered vector silently corrupts predictions."""
    return [features[name] for name in FEATURE_ORDER]


__all__ = ["FEATURE_ORDER", "extract_features", "to_vector"]
