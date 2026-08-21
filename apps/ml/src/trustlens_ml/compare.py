"""Trained model against the keyword heuristic, on in-domain text.

This exists because of what happened the first time the trained baseline was
pointed at a Pakistani marketplace advert.

`scam-clf-v1` scores **F1 0.906** on a held-out split of the corpora it was
trained on. Shown a listing reading *"Send advance payment via easypaisa to
confirm. WhatsApp me, no calls. Shipping today only, hurry!"* it returned
**p = 0.12, genuine** - a lower scam probability than it gave a completely
ordinary advert for a second-hand iPhone.

`FakeScamClassifier`, the ~30-line keyword stand-in written as a placeholder,
gets it right.

That comparison is the most useful result this package produces, so it is a
command rather than a story: anyone can re-run it, including an examiner.

**The probe set is synthetic and it is not a benchmark.** The rows in
`local_ads.example.csv` were written by hand to exercise known scam patterns,
not collected from a marketplace. Sixteen author-written examples cannot
measure accuracy - they can only demonstrate a failure this stark. Replacing
them with real collected ads is P7-02, and it remains the gate on using this
model for anything.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from trustlens.shared.logging import get_logger
from trustlens_ml.datasets.schema import Example

log = get_logger(__name__)


@dataclass(slots=True)
class Comparison:
    example: Example
    trained_probability: float
    trained_label: str
    keyword_probability: float
    keyword_label: str

    @property
    def trained_correct(self) -> bool:
        return (self.trained_label == "scam") == bool(self.example.label)

    @property
    def keyword_correct(self) -> bool:
        return (self.keyword_label == "scam") == bool(self.example.label)


async def compare(
    examples: list[Example], *, model_version: str, model_dir: Path
) -> list[Comparison]:
    from trustlens.ai.classifier.scam_classifier import TrainedScamClassifier
    from trustlens.ai.fakes import FakeScamClassifier

    trained = TrainedScamClassifier(model_version=model_version, model_dir=model_dir)
    keyword = FakeScamClassifier()

    results: list[Comparison] = []
    for example in examples:
        t = await trained.predict(
            title=example.title,
            description=example.description,
            price=example.price,
            category=example.category,
        )
        k = await keyword.predict(
            title=example.title,
            description=example.description,
            price=example.price,
            category=example.category,
        )
        results.append(
            Comparison(
                example=example,
                trained_probability=t.scam_probability,
                trained_label=t.label,
                keyword_probability=k.scam_probability,
                keyword_label=k.label,
            )
        )
    return results


def run(examples: list[Example], *, model_version: str, model_dir: Path) -> list[Comparison]:
    return asyncio.run(compare(examples, model_version=model_version, model_dir=model_dir))


def render(results: list[Comparison]) -> str:
    lines = [
        f"{'truth':<9}{'trained model':<24}{'keyword heuristic':<24}listing",
        "-" * 96,
    ]
    for r in results:
        truth = "scam" if r.example.label else "genuine"
        trained = (
            f"{r.trained_label} {r.trained_probability:.3f} "
            f"{'ok' if r.trained_correct else 'WRONG'}"
        )
        keyword = (
            f"{r.keyword_label} {r.keyword_probability:.3f} "
            f"{'ok' if r.keyword_correct else 'WRONG'}"
        )
        lines.append(f"{truth:<9}{trained:<24}{keyword:<24}{r.example.title[:34]}")

    total = len(results)
    trained_correct = sum(r.trained_correct for r in results)
    keyword_correct = sum(r.keyword_correct for r in results)
    scams = [r for r in results if r.example.label == 1]
    trained_caught = sum(r.trained_correct for r in scams)

    lines += [
        "-" * 96,
        f"correct:  trained {trained_correct}/{total}    keyword {keyword_correct}/{total}",
        f"scams caught:  trained {trained_caught}/{len(scams)}    "
        f"keyword {sum(r.keyword_correct for r in scams)}/{len(scams)}",
    ]

    if trained_caught == 0 and scams:
        lines += [
            "",
            "The trained model flagged NOTHING. On this domain it is a constant",
            "'genuine' predictor - the F1 of 0.906 it earned on English job",
            "adverts does not survive the move to Pakistani marketplace ads.",
            "It must not feed a seller's score until P7-02 provides real",
            "in-domain training data.",
        ]
    return "\n".join(lines)


__all__ = ["Comparison", "compare", "render", "run"]
