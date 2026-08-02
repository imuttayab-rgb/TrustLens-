"""P1-02 - measure CNIC OCR accuracy against hand-labelled ground truth.

Run this before tuning anything. The number it prints is the honest baseline,
and the tuned number after P1-03 is what goes in the report - a claim like
"our system reads CNICs accurately" is worth nothing without both.

Accuracy is reported per field and per condition (good light, glare, angled,
blurry), because the aggregate hides the thing that matters: a system that
scores 95% on clean scans and 20% on phone photos taken at night is a system
that fails in production, and only the per-condition split shows it.

Usage:
    uv run python apps/ml/bench/ocr_bench.py \
        --manifest apps/ml/datasets/cnic_manifest.csv \
        --images-dir apps/ml/datasets/cnic \
        --out apps/ml/results/ocr_baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bench.manifest import CnicSample, load_cnic_manifest
from trustlens.ai.ocr.cnic_validation import normalise_cnic, validate
from trustlens.ai.ocr.easyocr_engine import EasyOcrEngine

#: Fields scored by exact match after normalisation.
EXACT_FIELDS = ("cnic_number", "date_of_birth", "expiry_date")
#: Fields scored by both exact match and character similarity - OCR routinely
#: gets a name 90% right, and "wrong" is too blunt a verdict for that.
FUZZY_FIELDS = ("full_name", "father_name")

_PUNCT = re.compile(r"[^A-Z0-9 ]")


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(_PUNCT.sub(" ", str(value).upper()).split())


def _similarity(expected: Any, actual: Any) -> float:
    a, b = _norm_text(expected), _norm_text(actual)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _matches(fieldname: str, expected: Any, actual: Any) -> bool:
    if fieldname == "cnic_number":
        return bool(expected) and normalise_cnic(str(expected)) == normalise_cnic(
            str(actual) if actual else None
        )
    if expected is None:
        return actual is None
    return _norm_text(expected) == _norm_text(actual)


@dataclass
class FieldStat:
    attempted: int = 0
    correct: int = 0
    similarity_total: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.correct / self.attempted if self.attempted else 0.0

    @property
    def mean_similarity(self) -> float:
        return self.similarity_total / self.attempted if self.attempted else 0.0


async def run(
    samples: list[CnicSample], *, min_confidence: float, today: date | None = None
) -> dict[str, Any]:
    today = today or date.today()
    engine = EasyOcrEngine(min_confidence=min_confidence)

    overall: dict[str, FieldStat] = defaultdict(FieldStat)
    by_condition: dict[str, dict[str, FieldStat]] = defaultdict(lambda: defaultdict(FieldStat))
    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    confidences: list[float] = []
    review_cases = 0
    gender_checked = 0
    gender_consistent = 0

    for index, sample in enumerate(samples, start=1):
        print(f"  [{index}/{len(samples)}] {sample.image.name} ({sample.condition})", flush=True)

        started = time.perf_counter()
        result = await engine.extract(sample.image.read_bytes(), document_type="CNIC_FRONT")
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        confidences.append(result.confidence)

        row: dict[str, Any] = {
            "image": sample.image.name,
            "condition": sample.condition,
            "latency_ms": round(elapsed_ms, 1),
            "ocr_confidence": round(result.confidence, 4),
            "quality_score": result.quality_score,
            "fields": {},
        }

        for fieldname in (*EXACT_FIELDS, *FUZZY_FIELDS):
            expected = getattr(sample, fieldname)
            if expected is None:
                continue  # nothing to score against

            actual = getattr(result, fieldname)
            correct = _matches(fieldname, expected, actual)
            similarity = (
                _similarity(expected, actual) if fieldname in FUZZY_FIELDS else float(correct)
            )

            for bucket in (overall[fieldname], by_condition[sample.condition][fieldname]):
                bucket.attempted += 1
                bucket.correct += int(correct)
                bucket.similarity_total += similarity

            row["fields"][fieldname] = {
                "expected": str(expected),
                "actual": str(actual) if actual is not None else None,
                "correct": correct,
                "similarity": round(similarity, 3),
            }

        # The structural cross-checks from P1-04, exercised on real output.
        checks = validate(
            cnic_number=result.cnic_number,
            text=result.text,
            expiry=result.expiry_date,
            today=today,
        )
        row["validation"] = {
            "format_valid": checks.format_valid,
            "province": checks.province,
            "gender_from_number": checks.gender_from_number,
            "gender_from_text": checks.gender_from_text,
            "gender_consistent": checks.gender_consistent,
            "needs_manual_review": checks.needs_manual_review,
            "failures": list(checks.failures),
        }
        review_cases += int(checks.needs_manual_review)
        if checks.gender_consistent is not None:
            gender_checked += 1
            gender_consistent += int(checks.gender_consistent)

        rows.append(row)

    return {
        "sample_count": len(samples),
        "min_confidence": min_confidence,
        "overall": {
            name: {
                "attempted": stat.attempted,
                "accuracy": round(stat.accuracy, 4),
                "mean_similarity": round(stat.mean_similarity, 4),
            }
            for name, stat in sorted(overall.items())
        },
        "by_condition": {
            condition: {
                name: {
                    "attempted": stat.attempted,
                    "accuracy": round(stat.accuracy, 4),
                    "mean_similarity": round(stat.mean_similarity, 4),
                }
                for name, stat in sorted(stats.items())
            }
            for condition, stats in sorted(by_condition.items())
        },
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "max": round(max(latencies), 1) if latencies else 0.0,
        },
        "mean_ocr_confidence": (
            round(sum(confidences) / len(confidences), 4) if confidences else 0.0
        ),
        "manual_review_rate": round(review_cases / len(samples), 4) if samples else 0.0,
        "gender_cross_check": {
            "checked": gender_checked,
            "consistent": gender_consistent,
            "rate": round(gender_consistent / gender_checked, 4) if gender_checked else None,
        },
        "rows": rows,
    }


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 68)
    print(f"CNIC OCR BENCHMARK - {report['sample_count']} images")
    print("=" * 68)

    print("\nOverall accuracy by field")
    print(f"  {'field':<16} {'n':>4} {'exact':>8} {'similarity':>12}")
    for name, stat in report["overall"].items():
        print(
            f"  {name:<16} {stat['attempted']:>4} "
            f"{stat['accuracy'] * 100:>7.1f}% {stat['mean_similarity'] * 100:>11.1f}%"
        )

    print("\nAccuracy by condition")
    for condition, stats in report["by_condition"].items():
        print(f"  {condition}")
        for name, stat in stats.items():
            print(f"    {name:<16} {stat['attempted']:>4} {stat['accuracy'] * 100:>7.1f}%")

    gender = report["gender_cross_check"]
    print("\nStructural cross-checks")
    print(f"  gender digit vs printed field : {gender['checked']} checked, ", end="")
    print(f"{gender['rate'] * 100:.1f}% consistent" if gender["rate"] is not None else "n/a")
    print(f"  manual review rate            : {report['manual_review_rate'] * 100:.1f}%")

    print("\nPerformance")
    print(f"  mean latency  : {report['latency_ms']['mean']:.0f} ms")
    print(f"  max  latency  : {report['latency_ms']['max']:.0f} ms")
    print(f"  mean OCR conf : {report['mean_ocr_confidence'] * 100:.1f}%")

    target = report["overall"].get("cnic_number", {}).get("accuracy", 0.0)
    print("\n" + "-" * 68)
    print(
        f"P1-03 gate: CNIC number accuracy >= 90% on good-light images.  Now: {target * 100:.1f}%"
    )
    print("-" * 68)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None, help="Write the full report as JSON")
    parser.add_argument("--min-confidence", type=float, default=0.6)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        print("See apps/ml/datasets/README.md for how to build one.", file=sys.stderr)
        return 2

    samples = load_cnic_manifest(args.manifest, args.images_dir)
    if args.limit:
        samples = samples[: args.limit]
    if not samples:
        print("Manifest is empty.", file=sys.stderr)
        return 2

    print(f"Running EasyOCR over {len(samples)} images (first run downloads model weights)...")
    report = asyncio.run(run(samples, min_confidence=args.min_confidence))
    print_report(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nFull report written to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
