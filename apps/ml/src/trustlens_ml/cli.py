"""Command line for the training package.

    trustlens-ml fetch                 # download the public corpora
    trustlens-ml train                 # train, evaluate, export
    trustlens-ml inspect <version>     # what is inside an artifact
    trustlens-ml predict <version>     # score one listing from the terminal

`make -C apps/ml train` wraps the second one - that exact command is quoted in
the error the worker raises when the artifact is missing, so it has to work.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trustlens.shared.logging import configure_logging, get_logger
from trustlens_ml.compare import render
from trustlens_ml.compare import run as run_comparison
from trustlens_ml.datasets.loaders import fetch_all, load, load_local_ads
from trustlens_ml.datasets.schema import CORPORA
from trustlens_ml.evaluate import write_confusion_plot, write_plots, write_report
from trustlens_ml.train import cross_corpus_evaluate, save_bundle, train_baseline

log = get_logger(__name__)

ML_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ML_ROOT / "models"
REPORT_DIR = ML_ROOT / "reports"

DEFAULT_VERSION = "scamclf-v1"

#: Written out explicitly so an escape inside a nested f-string cannot turn
#: into a real line break in the emitted JSONL.
NEWLINE = chr(10)


def _fetch(args: argparse.Namespace) -> int:
    fetch_all(force=args.force)
    print("\nCorpora:")
    for spec in CORPORA.values():
        state = "downloadable" if spec.files else "MANUAL - see README"
        print(f"  {spec.key:<10} {spec.licence:<12} {state}")
        if spec.notes:
            print(f"             {spec.notes}")
    return 0


def _train(args: argparse.Namespace) -> int:
    examples = load(args.corpora)
    if not examples:
        print("No training data. Run `trustlens-ml fetch` first.", file=sys.stderr)
        return 1

    in_domain = load_local_ads() if args.evaluate_in_domain else []

    result = train_baseline(
        examples,
        model_version=args.version,
        in_domain=in_domain or None,
        target_precision=args.target_precision,
    )

    if args.cross_corpus:
        result.cross_corpus = cross_corpus_evaluate(
            examples, model_version=args.version, target_precision=args.target_precision
        )

    print()
    print(result.validation.summary())
    print(result.test.summary())
    if result.in_domain:
        print(result.in_domain.summary())
    else:
        print(
            "in-domain: NOT MEASURED - no hand-labelled Pakistani ads present "
            "(see apps/ml/README.md). Every number above is from a proxy corpus."
        )

    if result.cross_corpus:
        print("\nHeld-out corpus (never seen during training):")
        for evaluation in result.cross_corpus:
            print(f"  {evaluation.summary()}")
        print(
            "  ^ the gap against the in-corpus figures above is how much of the\n"
            "    headline number is specific to one dataset rather than to fraud."
        )

    print(f"\nOperating point: {result.rationale}")
    print("\nStrongest scam indicators learned:")
    for name, weight in result.top_features[:12]:
        print(f"  {weight:+.3f}  {name}")

    path = save_bundle(result, MODEL_DIR)
    print(f"\nArtifact: {path}")

    evaluations = [result.validation, result.test]
    if result.in_domain:
        evaluations.append(result.in_domain)
    evaluations.extend(result.cross_corpus)

    report = write_report(
        evaluations,
        REPORT_DIR / f"{args.version}-metrics.json",
        extra={
            "model_version": args.version,
            "top_features": result.top_features,
            "metadata": result.bundle.metadata,
        },
    )
    print(f"Metrics:  {report}")

    if args.plots and result.test_labels is not None and result.test_scores is not None:
        # The split carried out of training, not a fresh one. Re-splitting here
        # drew the figures on 7,750 rows while the table above described 7,339,
        # because training deduplicates before splitting and the caller did not.
        curves = {"tfidf+logreg (proxy test)": (result.test_labels, result.test_scores)}
        written = write_plots(curves, REPORT_DIR / "figures")
        confusion = write_confusion_plot(
            result.test, REPORT_DIR / "figures", name="tfidf+logreg (proxy test)"
        )
        if confusion:
            written.append(confusion)
        for plot in written:
            print(f"Figure:   {plot}")

    return 0


def _compare(args: argparse.Namespace) -> int:
    """Trained model vs the keyword heuristic on in-domain text (P7-05)."""
    examples = load_local_ads()
    if not examples:
        print("No in-domain listings found. See apps/ml/README.md.", file=sys.stderr)
        return 1
    print(render(run_comparison(examples, model_version=args.version, model_dir=MODEL_DIR)))
    return 0


def _export_jsonl(args: argparse.Namespace) -> int:
    """Write the exact splits the baseline used, for the Colab fine-tune.

    Same rows, same deduplication, same seed. Two models measured on two
    different test sets are not comparable however close the numbers look, and
    re-splitting inside the notebook is the easy way to make that mistake
    without noticing.
    """
    from trustlens_ml.train import deduplicate, split

    examples = deduplicate(load(args.corpora))
    parts = dict(zip(("train", "validation", "test"), split(examples), strict=True))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in parts.items():
        target = out / f"{name}.jsonl"
        with target.open("w", encoding="utf-8") as handle:
            for example in rows:
                record = {
                    "text": NEWLINE.join((example.title, example.description)).strip(),
                    "label": example.label,
                    "corpus": example.corpus,
                }
                handle.write(json.dumps(record) + NEWLINE)
        print(f"{target}  {len(rows)} rows, {sum(e.label for e in rows)} positive")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    from trustlens.ai.classifier.bundle import load as load_bundle

    bundle = load_bundle(MODEL_DIR / f"{args.version}.joblib")
    print(
        json.dumps(
            {
                "model_version": bundle.model_version,
                "format": bundle.format,
                "threshold": bundle.threshold,
                "features": len(bundle.feature_order),
                "metadata": bundle.metadata,
            },
            indent=2,
            default=str,
        )
    )
    return 0


def _predict(args: argparse.Namespace) -> int:
    from trustlens.ai.classifier.bundle import ListingRecord, predict_proba
    from trustlens.ai.classifier.bundle import load as load_bundle

    bundle = load_bundle(MODEL_DIR / f"{args.version}.joblib")
    record = ListingRecord(title=args.title, description=args.description)
    probability = float(predict_proba(bundle, [record])[0])
    verdict = "SCAM" if probability >= bundle.threshold else "genuine"
    print(f"{verdict}  p={probability:.4f}  (threshold {bundle.threshold:.2f})")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging(level="INFO", fmt="console", service="trustlens-ml", version="0.1.0")

    parser = argparse.ArgumentParser(prog="trustlens-ml", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fetch_cmd = sub.add_parser("fetch", help="download the public corpora")
    fetch_cmd.add_argument("--force", action="store_true", help="re-download cached files")
    fetch_cmd.set_defaults(handler=_fetch)

    train_cmd = sub.add_parser("train", help="train, evaluate and export the baseline")
    train_cmd.add_argument("--version", default=DEFAULT_VERSION)
    train_cmd.add_argument(
        "--corpora",
        nargs="+",
        default=["emscad", "difraud"],
        help="corpora to train on (default: emscad difraud)",
    )
    train_cmd.add_argument(
        "--target-precision",
        type=float,
        default=None,
        help=(
            "pick the highest-recall threshold holding at least this precision, "
            "instead of maximising F1"
        ),
    )
    train_cmd.add_argument(
        "--no-in-domain",
        dest="evaluate_in_domain",
        action="store_false",
        help="skip the in-domain evaluation even if local ads are present",
    )
    train_cmd.add_argument("--no-plots", dest="plots", action="store_false")
    train_cmd.add_argument(
        "--no-cross-corpus",
        dest="cross_corpus",
        action="store_false",
        help="skip the held-out-corpus check (it retrains once per corpus)",
    )
    train_cmd.set_defaults(handler=_train, evaluate_in_domain=True, plots=True, cross_corpus=True)

    compare_cmd = sub.add_parser(
        "compare", help="trained model vs the keyword heuristic on in-domain listings"
    )
    compare_cmd.add_argument("--version", default=DEFAULT_VERSION)
    compare_cmd.set_defaults(handler=_compare)

    export_cmd = sub.add_parser(
        "export-jsonl", help="write train/validation/test splits for the Colab fine-tune"
    )
    export_cmd.add_argument("--corpora", nargs="+", default=["emscad", "difraud"])
    export_cmd.add_argument("--out", default="apps/ml/reports/splits")
    export_cmd.set_defaults(handler=_export_jsonl)

    inspect_cmd = sub.add_parser("inspect", help="print an artifact's metadata")
    inspect_cmd.add_argument("version", nargs="?", default=DEFAULT_VERSION)
    inspect_cmd.set_defaults(handler=_inspect)

    predict_cmd = sub.add_parser("predict", help="score one listing")
    predict_cmd.add_argument("--version", default=DEFAULT_VERSION)
    predict_cmd.add_argument("--title", default="")
    predict_cmd.add_argument("--description", required=True)
    predict_cmd.set_defaults(handler=_predict)

    args = parser.parse_args(argv)
    handler = args.handler
    return int(handler(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
