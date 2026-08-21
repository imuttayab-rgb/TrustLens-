"""DistilBERT fine-tune, for a free Colab GPU (P7-04).

**Not run yet.** This is the script, not a result. Paste it into a Colab
notebook with a T4 runtime; it takes roughly 15-25 minutes on the combined
proxy corpora. Nothing in the deployed system imports it.

---

**Read the baseline's result before spending the GPU time.**

`tfidf+logreg` scored **F1 0.906** on a held-out split of these same corpora,
and then caught **1 of 7** scam listings on Pakistani marketplace text. The
bottleneck is not model capacity - it is that the training data is English job
adverts and the deployed task is Urdu-and-English ads for second-hand phones.

A transformer trained on the same corpora will very likely repeat the same
pattern: a better in-corpus number, the same collapse out of domain. That is
still worth measuring - "we tried the stronger model and the gap persisted" is
a real result, and the report asks for the comparison (P7-05) - but it is worth
measuring *knowing what it will probably show*, rather than hoping the
architecture rescues the data.

If GPU time is scarce, collecting the in-domain corpus (P7-02) buys more than
this does.

---

Export at the end is ONNX, matching the runtime the worker already carries for
OCR and face matching, so serving a transformer would not add a second heavy
dependency.
"""

# ruff: noqa: E402  (a notebook script: linear, prints, installs first)
from __future__ import annotations

# ── Colab setup ──────────────────────────────────────────────────────
# !pip install -q transformers datasets accelerate evaluate onnxruntime optimum[onnxruntime]
import json
from pathlib import Path

import numpy as np

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256  # adverts are short; 256 tokens covers the corpora's 95th percentile
SEED = 20260822
OUTPUT_DIR = Path("distilbert-scam")

# ── 1. Data ──────────────────────────────────────────────────────────
# Upload the JSONL produced by:  trustlens-ml export-jsonl
# It carries the SAME rows, the SAME deduplication and the SAME split as the
# baseline. Re-splitting here would make the comparison meaningless: two models
# measured on two different test sets are not comparable, however similar the
# numbers look.


def load_split(path: str) -> list[dict[str, object]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


train_rows = load_split("train.jsonl")
validation_rows = load_split("validation.jsonl")
test_rows = load_split("test.jsonl")

print(f"train {len(train_rows)}  validation {len(validation_rows)}  test {len(test_rows)}")
print(f"positives in train: {sum(r['label'] for r in train_rows)}")

# ── 2. Tokenise ──────────────────────────────────────────────────────
from datasets import Dataset
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)


def encode(batch: dict[str, list]) -> dict[str, list]:
    return tokenizer(batch["text"], truncation=True, padding="max_length", max_length=MAX_LENGTH)


datasets = {
    name: Dataset.from_list(rows).map(encode, batched=True)
    for name, rows in (
        ("train", train_rows),
        ("validation", validation_rows),
        ("test", test_rows),
    )
}

# ── 3. Train ─────────────────────────────────────────────────────────
import torch
from torch import nn
from transformers import (
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
)

model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

# The corpus is ~20:1 genuine. Without a weighted loss the model minimises
# cross-entropy by predicting "genuine" everywhere - the same trap
# `class_weight="balanced"` handles for the baseline.
positive_count = max(sum(int(r["label"]) for r in train_rows), 1)
negative_count = max(len(train_rows) - positive_count, 1)
class_weights = torch.tensor([1.0, negative_count / positive_count], dtype=torch.float)
print(f"positive class weight: {class_weights[1]:.2f}")


class WeightedTrainer(Trainer):
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):  # type: ignore[no-untyped-def]
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = nn.CrossEntropyLoss(weight=class_weights.to(outputs.logits.device))(
            outputs.logits, labels
        )
        return (loss, outputs) if return_outputs else loss


def compute_metrics(prediction) -> dict[str, float]:  # type: ignore[no-untyped-def]
    from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score

    logits, labels = prediction
    probabilities = torch.softmax(torch.tensor(logits), dim=1)[:, 1].numpy()
    predicted = (probabilities >= 0.5).astype(int)
    return {
        "f1": float(f1_score(labels, predicted, zero_division=0)),
        "precision": float(precision_score(labels, predicted, zero_division=0)),
        "recall": float(recall_score(labels, predicted, zero_division=0)),
        # The honest summary under imbalance. Reported first for that reason.
        "pr_auc": float(average_precision_score(labels, probabilities)),
    }


trainer = WeightedTrainer(
    model=model,
    args=TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=3,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=64,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        # PR-AUC, not accuracy: at 4.8% positives accuracy would pick the
        # checkpoint that learned to say "genuine".
        metric_for_best_model="pr_auc",
        greater_is_better=True,
        seed=SEED,
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        report_to=[],
    ),
    train_dataset=datasets["train"],
    eval_dataset=datasets["validation"],
    compute_metrics=compute_metrics,
)

trainer.train()

# ── 4. Evaluate, once, on the held-out split ─────────────────────────
test_metrics = trainer.evaluate(datasets["test"])
print(json.dumps(test_metrics, indent=2))

# Copy these into apps/ml/reports/ next to the baseline's numbers, and put BOTH
# in the report. If DistilBERT wins only narrowly, the baseline is still the
# better thing to deploy: its coefficients can be read out in an appeal, and
# ADR-0002 makes explainability a product requirement rather than a preference.
(OUTPUT_DIR / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2))

# ── 5. Export to ONNX ────────────────────────────────────────────────
# The worker already runs onnxruntime for OCR and face matching, so a
# transformer served this way costs no new dependency - only ~250 MB of weights
# and a slower forward pass on a shared CPU.
from optimum.onnxruntime import ORTModelForSequenceClassification

ort_model = ORTModelForSequenceClassification.from_pretrained(OUTPUT_DIR, export=True)
ort_model.save_pretrained(OUTPUT_DIR / "onnx")
tokenizer.save_pretrained(OUTPUT_DIR / "onnx")
print(f"ONNX written to {OUTPUT_DIR / 'onnx'}")

# ── 6. Wiring it in ──────────────────────────────────────────────────
# Serving this would need a new adapter implementing the same ScamClassifier
# port - `trustlens/ai/classifier/distilbert_classifier.py`, selected by a
# setting exactly as OCR_ENGINE and FACE_ENGINE already are. Do NOT change the
# port: the whole point of ports/adapters here is that a model swap is one new
# file and one branch in factory.py.
#
# Do not wire it in before the in-domain evaluation exists. A model that scores
# well on job adverts and is silently trusted on marketplace ads is worse than
# no model, because the score it feeds is one a seller has to appeal.
_ = np  # silence the unused-import lint in this linear script
