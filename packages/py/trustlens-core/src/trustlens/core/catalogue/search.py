"""Bounded literal search tokens; plus variants stay distinct from base models."""
import re


def search_tokens(query: str) -> list[str]:
    normalized = re.sub(r"(?<=\d)\s*\+", " plus ", query.casefold())
    normalized = re.sub(r"\bs\s+(\d{1,3})\b", r"s\1", normalized)
    return list(dict.fromkeys(re.findall(r"[^\W_]+", normalized)))[:12]
