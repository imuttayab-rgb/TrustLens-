"""P1-07 - measure selfie-to-CNIC face match accuracy and choose a threshold.

The threshold is the whole decision. Set it too low and a scammer's selfie
passes against someone else's CNIC; too high and honest sellers are rejected by
their own ID photo - which is worse, because CNIC photographs are often years
old, low resolution, and printed.

So this does not report a single accuracy figure. It sweeps every threshold and
reports the error trade-off at each, letting you pick deliberately rather than
inheriting DeepFace's default.

Two error rates, and they are not symmetrical:
  FAR (false accept) - different people scored as a match. A security failure.
  FRR (false reject) - the same person scored as a mismatch. A usability
                       failure that generates appeals and support load.

Usage:
    uv run python apps/ml/bench/face_bench.py \
        --manifest apps/ml/datasets/face_manifest.csv \
        --images-dir apps/ml/datasets/faces \
        --out apps/ml/results/face_baseline.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bench.manifest import FacePair, load_face_manifest
from trustlens.ai.face.deepface_matcher import DeepFaceMatcher

#: Similarity thresholds to sweep. The adapter converts DeepFace's distance
#: into a 0..1 similarity, so higher is always stricter.
SWEEP = tuple(round(x / 100, 2) for x in range(30, 96, 5))


@dataclass(frozen=True, slots=True)
class Measurement:
    document: str
    selfie: str
    same_person: bool
    condition: str
    similarity: float
    distance: float
    face_found: bool
    latency_ms: float
    error: str | None = None


async def measure(pairs: list[FacePair], *, model: str, detector: str) -> list[Measurement]:
    matcher = DeepFaceMatcher(model_name=model, detector_backend=detector)
    out: list[Measurement] = []

    for index, pair in enumerate(pairs, start=1):
        label = "same" if pair.same_person else "different"
        print(
            f"  [{index}/{len(pairs)}] {pair.document_image.name} vs "
            f"{pair.selfie_image.name} ({label})",
            flush=True,
        )

        started = time.perf_counter()
        result = await matcher.compare(
            pair.document_image.read_bytes(),
            pair.selfie_image.read_bytes(),
            threshold=0.5,  # irrelevant here; the sweep applies its own
        )
        elapsed_ms = (time.perf_counter() - started) * 1000

        face_found = result.face_detected_in_document and result.face_detected_in_selfie
        out.append(
            Measurement(
                document=pair.document_image.name,
                selfie=pair.selfie_image.name,
                same_person=pair.same_person,
                condition=pair.condition,
                similarity=result.similarity,
                distance=result.distance,
                face_found=face_found,
                latency_ms=round(elapsed_ms, 1),
                error=result.raw.get("error"),
            )
        )

    return out


def sweep(measurements: list[Measurement]) -> list[dict[str, Any]]:
    """Error rates at each candidate threshold.

    Pairs where no face was detected are excluded: that is an image-quality
    problem the seller can fix by retaking the photo, not a matching error, and
    folding it in would make every threshold look equally bad.
    """
    usable = [m for m in measurements if m.face_found]
    same = [m for m in usable if m.same_person]
    different = [m for m in usable if not m.same_person]

    rows: list[dict[str, Any]] = []
    for threshold in SWEEP:
        false_rejects = sum(1 for m in same if m.similarity < threshold)
        false_accepts = sum(1 for m in different if m.similarity >= threshold)
        frr = false_rejects / len(same) if same else 0.0
        far = false_accepts / len(different) if different else 0.0
        correct = (len(same) - false_rejects) + (len(different) - false_accepts)
        rows.append(
            {
                "threshold": threshold,
                "false_accepts": false_accepts,
                "false_rejects": false_rejects,
                "far": round(far, 4),
                "frr": round(frr, 4),
                "accuracy": round(correct / len(usable), 4) if usable else 0.0,
                "balanced_error": round((far + frr) / 2, 4),
            }
        )
    return rows


def recommend(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer the strictest threshold that admits no impostor.

    Identity verification is the signal the whole Trust Score leans on, and a
    false accept is unrecoverable - a scammer verified against a stranger's
    CNIC now carries a high score. A false reject only costs an appeal, which
    the system already supports. So zero-FAR wins, and among those, the lowest
    FRR.
    """
    zero_far = [r for r in rows if r["false_accepts"] == 0]
    if zero_far:
        return min(zero_far, key=lambda r: (r["frr"], -r["threshold"]))
    return min(rows, key=lambda r: r["balanced_error"]) if rows else None


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 68)
    print(f"FACE MATCH BENCHMARK - {report['pair_count']} pairs")
    print(f"model={report['model']}  detector={report['detector']}")
    print("=" * 68)

    detection = report["detection"]
    print(
        f"\nFace detection: {detection['found']}/{detection['total']} pairs usable"
        f"  ({detection['failure_rate'] * 100:.1f}% unusable)"
    )
    if detection["failures"]:
        print("  Undetected in:")
        for name in detection["failures"]:
            print(f"    - {name}")

    print("\nThreshold sweep")
    print(f"  {'thresh':>7} {'FAR':>8} {'FRR':>8} {'acc':>8}   {'FA':>3} {'FR':>3}")
    for row in report["sweep"]:
        marker = "  <-- recommended" if row["threshold"] == report["recommended"] else ""
        print(
            f"  {row['threshold']:>7.2f} {row['far'] * 100:>7.1f}% {row['frr'] * 100:>7.1f}% "
            f"{row['accuracy'] * 100:>7.1f}%   {row['false_accepts']:>3} "
            f"{row['false_rejects']:>3}{marker}"
        )

    separation = report["separation"]
    print("\nSimilarity separation")
    print(
        f"  same person      : min {separation['same_min']:.3f}  mean {separation['same_mean']:.3f}"
    )
    print(
        f"  different people : max {separation['different_max']:.3f}  "
        f"mean {separation['different_mean']:.3f}"
    )
    gap = separation["gap"]
    print(f"  gap              : {gap:+.3f}", end="")
    print("  (negative = the classes overlap; no threshold separates them cleanly)")

    print("\nPerformance")
    print(f"  mean latency : {report['latency_ms']['mean']:.0f} ms")
    print(f"  max  latency : {report['latency_ms']['max']:.0f} ms")

    print("\n" + "-" * 68)
    if report["recommended"] is not None:
        chosen = next(r for r in report["sweep"] if r["threshold"] == report["recommended"])
        print(
            f"Recommended threshold: {report['recommended']:.2f}  "
            f"(FAR {chosen['far'] * 100:.1f}%, FRR {chosen['frr'] * 100:.1f}%)"
        )
        print("Set FACE_MATCH_THRESHOLD to this value, and record it in the report.")
    else:
        print("No threshold could be recommended - not enough usable pairs.")
    print("-" * 68)


def build_report(measurements: list[Measurement], *, model: str, detector: str) -> dict[str, Any]:
    usable = [m for m in measurements if m.face_found]
    same = [m.similarity for m in usable if m.same_person]
    different = [m.similarity for m in usable if not m.same_person]
    rows = sweep(measurements)
    best = recommend(rows)
    latencies = [m.latency_ms for m in measurements]

    return {
        "pair_count": len(measurements),
        "model": model,
        "detector": detector,
        "detection": {
            "total": len(measurements),
            "found": len(usable),
            "failure_rate": (
                round(1 - len(usable) / len(measurements), 4) if measurements else 0.0
            ),
            "failures": [f"{m.document} / {m.selfie}" for m in measurements if not m.face_found],
        },
        "separation": {
            "same_min": min(same) if same else 0.0,
            "same_mean": sum(same) / len(same) if same else 0.0,
            "different_max": max(different) if different else 0.0,
            "different_mean": sum(different) / len(different) if different else 0.0,
            "gap": (min(same) - max(different)) if same and different else 0.0,
        },
        "sweep": rows,
        "recommended": best["threshold"] if best else None,
        "latency_ms": {
            "mean": round(sum(latencies) / len(latencies), 1) if latencies else 0.0,
            "max": round(max(latencies), 1) if latencies else 0.0,
        },
        "measurements": [m.__dict__ for m in measurements],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--model", default="ArcFace")
    parser.add_argument("--detector", default="retinaface")
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        print("See apps/ml/datasets/README.md for how to build one.", file=sys.stderr)
        return 2

    pairs = load_face_manifest(args.manifest, args.images_dir)
    if not pairs:
        print("Manifest is empty.", file=sys.stderr)
        return 2

    same_count = sum(1 for p in pairs if p.same_person)
    if same_count == 0 or same_count == len(pairs):
        print(
            "Manifest needs both matching and non-matching pairs to measure "
            "false accepts and false rejects.",
            file=sys.stderr,
        )
        return 2

    print(f"Comparing {len(pairs)} pairs (first run downloads model weights)...")
    measurements = asyncio.run(measure(pairs, model=args.model, detector=args.detector))
    report = build_report(measurements, model=args.model, detector=args.detector)
    print_report(report)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"\nFull report written to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
