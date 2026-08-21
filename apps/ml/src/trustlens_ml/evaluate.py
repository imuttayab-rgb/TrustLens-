"""Metrics, threshold selection and plots (P7-05).

**Accuracy is not reported as a headline number, and that is deliberate.** The
EMSCAD corpus is 4.8% fraudulent, so a model that predicts "genuine" for every
advert scores 95.2% accurate and catches nothing. Quoting that figure would
flatter the project and mislead the reader, so accuracy appears only alongside
the majority-class baseline that exposes it.

What matters instead:

* **Precision** - of the listings we flag, how many really are scams. This is
  the cost a seller pays for a false accusation.
* **Recall** - of the real scams, how many we catch. This is the cost a buyer
  pays for a miss.
* **PR-AUC** (average precision) - the honest summary under class imbalance.
  ROC-AUC is reported too because the report asks for it, but a ROC curve
  looks reassuring on imbalanced data long after the model has stopped being
  useful.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from trustlens.shared.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ThresholdPoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    flagged: int


@dataclass(slots=True)
class Evaluation:
    """Everything the report needs about one model on one split."""

    model: str
    corpus: str
    rows: int
    positives: int
    threshold: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    accuracy: float
    majority_class_accuracy: float
    confusion: dict[str, int]
    sweep: list[ThresholdPoint] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sweep"] = [asdict(p) for p in self.sweep]
        return data

    def summary(self) -> str:
        return (
            f"{self.model} on {self.corpus}: "
            f"P={self.precision:.3f} R={self.recall:.3f} F1={self.f1:.3f} "
            f"PR-AUC={self.pr_auc:.3f} ROC-AUC={self.roc_auc:.3f} "
            f"(accuracy {self.accuracy:.3f} vs {self.majority_class_accuracy:.3f} "
            f"for always-genuine)"
        )


def sweep_thresholds(
    y_true: np.ndarray, scores: np.ndarray, *, steps: int = 19
) -> list[ThresholdPoint]:
    """Precision and recall across the operating range.

    Reported rather than reduced to one number, because the choice of operating
    point is a product decision, not a modelling one - and the report has to be
    able to show that the choice was made with the curve in view.
    """
    from sklearn.metrics import precision_score, recall_score

    points: list[ThresholdPoint] = []
    for threshold in np.linspace(0.05, 0.95, steps):
        predicted = (scores >= threshold).astype(int)
        points.append(
            ThresholdPoint(
                threshold=round(float(threshold), 3),
                precision=round(float(precision_score(y_true, predicted, zero_division=0)), 4),
                recall=round(float(recall_score(y_true, predicted, zero_division=0)), 4),
                f1=round(float(_f1(y_true, predicted)), 4),
                flagged=int(predicted.sum()),
            )
        )
    return points


def _f1(y_true: np.ndarray, predicted: np.ndarray) -> float:
    from sklearn.metrics import f1_score

    return float(f1_score(y_true, predicted, zero_division=0))


def choose_threshold(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    target_precision: float | None = None,
) -> tuple[float, str]:
    """Pick the operating point, and say why it was picked.

    Default is the F1-maximising threshold. Pass `target_precision` to instead
    take the highest-recall point that still meets a precision floor - the
    right call if the product decides that wrongly flagging a genuine seller is
    the more expensive error.

    Returns (threshold, rationale) so the reason travels into the artifact and
    can be quoted in an appeal months later.
    """
    points = sweep_thresholds(y_true, scores, steps=91)

    if target_precision is not None:
        eligible = [p for p in points if p.precision >= target_precision and p.flagged > 0]
        if eligible:
            best = max(eligible, key=lambda p: p.recall)
            return best.threshold, (
                f"highest recall ({best.recall:.3f}) among thresholds holding "
                f"precision >= {target_precision:.2f}; chosen precision "
                f"{best.precision:.3f}"
            )
        log.warning("target_precision_unreachable", target=target_precision)

    best = max(points, key=lambda p: p.f1)
    return best.threshold, (
        f"maximises F1 ({best.f1:.3f}) on the validation split; "
        f"precision {best.precision:.3f}, recall {best.recall:.3f}"
    )


def evaluate(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    threshold: float,
    model: str,
    corpus: str,
    notes: str = "",
) -> Evaluation:
    from sklearn.metrics import (
        accuracy_score,
        average_precision_score,
        confusion_matrix,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    predicted = (scores >= threshold).astype(int)
    positives = int(y_true.sum())
    majority = 1.0 - (positives / len(y_true)) if len(y_true) else 0.0

    # A split with one class present makes AUC undefined; report NaN rather
    # than crashing a training run over a degenerate slice.
    both_classes = 0 < positives < len(y_true)
    tn, fp, fn, tp = (
        confusion_matrix(y_true, predicted, labels=[0, 1]).ravel() if len(y_true) else (0, 0, 0, 0)
    )

    return Evaluation(
        model=model,
        corpus=corpus,
        rows=len(y_true),
        positives=positives,
        threshold=round(float(threshold), 4),
        precision=round(float(precision_score(y_true, predicted, zero_division=0)), 4),
        recall=round(float(recall_score(y_true, predicted, zero_division=0)), 4),
        f1=round(_f1(y_true, predicted), 4),
        roc_auc=round(float(roc_auc_score(y_true, scores)), 4) if both_classes else float("nan"),
        pr_auc=(
            round(float(average_precision_score(y_true, scores)), 4)
            if both_classes
            else float("nan")
        ),
        accuracy=round(float(accuracy_score(y_true, predicted)), 4),
        majority_class_accuracy=round(float(majority), 4),
        confusion={"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        sweep=sweep_thresholds(y_true, scores),
        notes=notes,
    )


def write_report(evaluations: list[Evaluation], path: Path, *, extra: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {**extra, "evaluations": [e.to_dict() for e in evaluations]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("report_written", path=str(path))
    return path


def write_plots(curves: dict[str, tuple[np.ndarray, np.ndarray]], out_dir: Path) -> list[Path]:
    """Confusion matrix, ROC and precision-recall curves, for the report.

    Written as PNG at print resolution. Returns an empty list when matplotlib
    is not installed rather than failing the training run - the metrics JSON is
    the artifact that matters, and the plots are generated from it.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from sklearn.metrics import PrecisionRecallDisplay, RocCurveDisplay
    except ImportError:
        log.warning("matplotlib_missing_skipping_plots")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, (y_true, scores) in curves.items():
        if not (0 < int(y_true.sum()) < len(y_true)):
            continue

        fig, ax = plt.subplots(figsize=(5, 4), dpi=200)
        PrecisionRecallDisplay.from_predictions(y_true, scores, ax=ax, name=name)
        # The line a random model would sit on. Without it a PR curve on a
        # 4.8%-positive corpus looks far better than it is.
        ax.axhline(
            float(y_true.mean()),
            linestyle="--",
            linewidth=1,
            color="grey",
            label=f"chance ({y_true.mean():.3f})",
        )
        ax.set_title(f"Precision-recall - {name}")
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        target = out_dir / f"pr_curve_{_slug(name)}.png"
        fig.savefig(target)
        plt.close(fig)
        written.append(target)

        fig, ax = plt.subplots(figsize=(5, 4), dpi=200)
        RocCurveDisplay.from_predictions(y_true, scores, ax=ax, name=name)
        ax.plot([0, 1], [0, 1], linestyle="--", linewidth=1, color="grey")
        ax.set_title(f"ROC - {name}")
        fig.tight_layout()
        target = out_dir / f"roc_curve_{_slug(name)}.png"
        fig.savefig(target)
        plt.close(fig)
        written.append(target)

    log.info("plots_written", count=len(written), dir=str(out_dir))
    return written


def write_confusion_plot(evaluation: Evaluation, out_dir: Path, *, name: str) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    c = evaluation.confusion
    matrix = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]])

    fig, ax = plt.subplots(figsize=(4, 3.6), dpi=200)
    ax.imshow(matrix, cmap="Blues")
    ax.set_xticks([0, 1], ["predicted genuine", "predicted scam"])
    ax.set_yticks([0, 1], ["actually genuine", "actually scam"])
    for (row, col), value in np.ndenumerate(matrix):
        ax.text(
            col,
            row,
            f"{value:,}",
            ha="center",
            va="center",
            color="white" if value > matrix.max() / 2 else "black",
        )
    ax.set_title(f"Confusion at threshold {evaluation.threshold:.2f}\n{name}", fontsize=9)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"confusion_{_slug(name)}.png"
    fig.savefig(target)
    plt.close(fig)
    return target


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in value.lower()).strip("_")


__all__ = [
    "Evaluation",
    "ThresholdPoint",
    "choose_threshold",
    "evaluate",
    "sweep_thresholds",
    "write_confusion_plot",
    "write_plots",
    "write_report",
]
