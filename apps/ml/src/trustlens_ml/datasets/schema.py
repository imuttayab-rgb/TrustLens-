"""One shape for every corpus, and the registry of where they come from.

Three corpora feed this classifier, and they are not equal. Two are **proxies**
- public English-language fraud datasets that stand in for data TrustLens does
not have - and one is the real thing, hand-labelled Pakistani marketplace ads.

Keeping the distinction in the type rather than in a comment is deliberate.
Every metric this project reports has to say which corpus produced it, because
a number from a proxy corpus does not transfer to Karachi mobile-phone listings
and quoting it as though it does would be the single most misleading thing this
report could do.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Provenance(StrEnum):
    """Where a corpus came from, and therefore what its numbers are worth."""

    #: Public dataset from another fraud domain. Useful for learning what
    #: deceptive writing looks like; NOT evidence of performance on TrustLens
    #: listings.
    PROXY = "PROXY"
    #: Hand-labelled Pakistani marketplace ads. Small, but the only corpus whose
    #: numbers describe the deployed task.
    IN_DOMAIN = "IN_DOMAIN"


@dataclass(frozen=True, slots=True)
class Example:
    """A labelled listing-like document.

    `title` and `description` are separated rather than concatenated because
    the shared feature extractor treats them differently, and because a corpus
    that has no title (an SMS, say) should say so with an empty string instead
    of silently borrowing the first line of the body.
    """

    title: str
    description: str
    label: int  # 1 = scam / fraudulent, 0 = genuine
    corpus: str
    provenance: Provenance
    price: float | None = None
    category: str | None = None

    def __post_init__(self) -> None:
        if self.label not in (0, 1):
            raise ValueError(f"label must be 0 or 1, got {self.label!r}")


@dataclass(frozen=True, slots=True)
class CorpusSpec:
    """How to obtain one corpus, and what it is allowed to be used for."""

    key: str
    title: str
    provenance: Provenance
    licence: str
    url: str
    #: Files to download, as (remote path, local filename).
    files: tuple[tuple[str, str], ...]
    notes: str = ""


HF = "https://huggingface.co/datasets"

#: The ~18k-row EMSCAD set (P7-02). CC0, so it can be used and described in an
#: academic report without a licence problem.
EMSCAD = CorpusSpec(
    key="emscad",
    title="Real / Fake Job Postings (EMSCAD)",
    provenance=Provenance.PROXY,
    licence="CC0-1.0",
    url=f"{HF}/victor/real-or-fake-fake-jobposting-prediction",
    files=(
        (
            f"{HF}/victor/real-or-fake-fake-jobposting-prediction/resolve/main/fake_job_postings.csv",
            "emscad/fake_job_postings.csv",
        ),
    ),
    notes=(
        "17,880 rows, 866 fraudulent (4.8%). English recruitment ads, not "
        "marketplace listings for physical goods - the closest large public "
        "corpus, not the same task."
    ),
)

#: DIFrauD, MIT licensed, already split. Only the two domains whose writing
#: resembles a marketplace scam are used; `product_reviews` and
#: `political_statements` are different problems wearing the same label name.
DIFRAUD = CorpusSpec(
    key="difraud",
    title="DIFrauD (job_scams + sms)",
    provenance=Provenance.PROXY,
    licence="MIT",
    url=f"{HF}/redasers/difraud",
    files=tuple(
        (
            f"{HF}/redasers/difraud/resolve/main/{domain}/{split}.jsonl",
            f"difraud/{domain}_{split}.jsonl",
        )
        for domain in ("job_scams", "sms")
        for split in ("train", "validation", "test")
    ),
    notes=(
        "Deceptive-text corpus across several fraud domains. Only job_scams "
        "and sms are loaded: product_reviews is deceptive-review detection and "
        "political_statements is fact-checking, neither of which is this task."
    ),
)

#: The one that actually matters, and the one that does not exist yet.
LOCAL_ADS = CorpusSpec(
    key="local_ads",
    title="Hand-labelled Pakistani marketplace ads",
    provenance=Provenance.IN_DOMAIN,
    licence="Collected by the project team",
    url="apps/ml/datasets/local_ads/local_ads.csv",
    files=(),
    notes=(
        "A human task, like P1-01. Nothing downloadable substitutes for it: it "
        "is the only corpus that can answer 'does this work on OLX Pakistan'."
    ),
)

CORPORA: dict[str, CorpusSpec] = {c.key: c for c in (EMSCAD, DIFRAUD, LOCAL_ADS)}


__all__ = [
    "CORPORA",
    "DIFRAUD",
    "EMSCAD",
    "LOCAL_ADS",
    "CorpusSpec",
    "Example",
    "Provenance",
]
