# apps/ml — the scam-listing classifier

Training, evaluation and export for TrustLens's custom model (Phase 7). Nothing
here is imported at runtime: the worker loads the exported artifact through
`trustlens.ai`, and an import-linter contract fails the build if that ever stops
being true.

```bash
make -C apps/ml fetch     # download the public corpora (~50 MB)
make -C apps/ml train     # train, evaluate, export  (~3 minutes on a laptop)
make -C apps/ml compare   # trained model vs the keyword heuristic
```

---

## The result, stated plainly

**The trained classifier scores F1 0.906 on held-out data, and it does not work
on TrustLens listings.**

Both halves of that sentence are true, and the second one is the finding.

| Measured on                            | Precision | Recall                  | F1        | PR-AUC |
| -------------------------------------- | --------- | ----------------------- | --------- | ------ |
| Held-out split of the training corpora | 0.918     | 0.894                   | **0.906** | 0.962  |
| A fraud corpus it was never trained on | 0.698     | 0.665                   | **0.681** | 0.708  |
| A different one, same test             | 0.320     | 0.714                   | **0.442** | 0.312  |
| Pakistani marketplace ads              | —         | **1 of 7 scams caught** | —         | —      |

The last row is what the deployed system would see. Shown an advert reading
_"Send advance payment via easypaisa to confirm. WhatsApp me, no calls.
Shipping today only, hurry!"_, the model returns **p = 0.13, genuine** — a
lower scam probability than it assigns to an unremarkable listing for a
second-hand iPhone.

The 30-line keyword heuristic written as a placeholder (`FakeScamClassifier`)
catches 4 of those 7. It is not good either. It is better than the model that
scores 0.906.

### Why

The corpora are English-language **job adverts** and scam SMS. TrustLens scores
Urdu-and-English **marketplace ads for physical goods** in Pakistan. The model
learned what fraud looks like _in recruitment_, and its strongest learned
indicators say so:

```
+6.17  text          +5.92  link            +5.92  using below
+5.90  below link    +5.90  txt             +5.64  apply using
+5.17  assistant     +4.46  clerk           +4.34  offshore
```

`apply using the below link` is the boilerplate of a fake job posting. It will
never appear in an advert for a used Honda Civic. None of the vocabulary that
matters for this product — `easypaisa`, `jazzcash`, `token money`, `advance`,
`bank transfer only`, `no meetup` — could be learned, because no training
example contained it.

### What follows

1. **The number in the report is the cross-corpus one, not 0.906.** Quoting
   0.906 as "TrustLens detects scam listings with 91% accuracy" would be the
   single most misleading sentence the project could publish.
2. **This model must not feed a seller's score yet.** `jobs/listings.py`
   combines it as `max(llm_risk, classifier_probability × 100)`, so a false
   positive is not averaged away — it _becomes_ the listing's risk, and flows
   into a trust score the seller then has to appeal.
3. **The fix is data, not architecture.** A bigger model trained on the same
   corpora will very likely reproduce the same gap. See
   [`notebooks/distilbert_colab.py`](notebooks/distilbert_colab.py), which says
   so at the top.

---

## Collecting the corpus that would fix it (P7-02)

This is a human task, like the CNIC images in P1-01, and it is the gate on
everything above.

**Target:** 300–500 real listings from OLX Pakistan or similar, roughly 20–30%
scams. Fewer is still useful; 50 labelled ads would already tell you more than
36,695 job adverts did.

**How to label.** A listing is `1` (scam) if it shows a pattern a buyer would
lose money to:

- payment before inspection — advance, token money, deposit, "50% now"
- refusing a meetup, or "I am out of city, will courier after payment"
- pushing off-platform — "WhatsApp only", "contact on Telegram"
- a price far below market for the item's condition
- manufactured urgency or scarcity — "today only", "last one", "no bargaining"

A listing is `0` (genuine) if it reads like an ordinary sale. Include hard
genuine cases: real sellers write in capitals, real sellers say "urgent sale"
because they are moving house. If every genuine example is calm and
well-punctuated, the model learns to detect punctuation.

**Format.** Copy [`datasets/local_ads/local_ads.example.csv`](datasets/local_ads/local_ads.example.csv)
to `datasets/local_ads/local_ads.csv` and fill it in. Columns: `title`,
`description`, `price`, `category`, `label`, `note`. The `.gitignore` in
`datasets/` tracks only the example file, so real collected data stays local —
the same rule the CNIC benchmark follows.

> ⚠️ The example file is **sixteen rows written by hand** to exercise known scam
> patterns. It is a smoke test, not a benchmark: it can demonstrate a failure
> as stark as the one above, and it cannot measure accuracy. It is not a
> substitute for collecting real ads, and no number derived from it belongs in
> the report as a result.

Once `local_ads.csv` exists, `make -C apps/ml train` picks it up automatically
and reports an in-domain line beside the proxy figures.

---

## What the pipeline does

| Stage            | Module                           | Notes                                               |
| ---------------- | -------------------------------- | --------------------------------------------------- |
| Fetch            | `datasets/loaders.py`            | Cached on disk; re-runs are offline                 |
| Normalise        | `datasets/schema.py`             | One `Example` shape; provenance is part of the type |
| Deduplicate      | `train.py`                       | 2,054 exact duplicates dropped before splitting     |
| Split            | `train.py`                       | Stratified 60/20/20, fixed seed `20260822`          |
| Vectorise        | `trustlens.ai.classifier.bundle` | Shared with inference — see below                   |
| Train            | `train.py`                       | Logistic regression, `class_weight="balanced"`      |
| Choose threshold | `evaluate.py`                    | On **validation**; test is scored once, after       |
| Evaluate         | `evaluate.py`                    | Precision/recall/F1/PR-AUC + cross-corpus + plots   |
| Export           | `bundle.py`                      | joblib bundle with metrics and threshold attached   |

### Three things it is built not to do

**Leak through duplicates.** Public fraud corpora repeat adverts. A duplicate
straddling the split is the model being asked a question it was given the
answer to, and it shows up as a good score rather than an error. 2,054 rows
were dropped.

**Pick a threshold on the test set.** The operating point is chosen against the
validation curve and stored in the artifact; the test split is scored once,
afterwards, with that threshold already fixed.

**Skew between training and serving.** `bundle.py` holds the only path from a
listing to a feature vector, and both training and the worker call it. This is
the classic way a model scores 0.94 offline and behaves randomly in production,
and a test asserts the two produce identical matrices.

### Why accuracy is not the headline

The corpus is 7% fraudulent, so predicting "genuine" for everything scores
**93% accurate** and catches nothing. Every accuracy figure this package prints
is followed by that majority-class number, and a unit test asserts the
evaluation still exposes it.

---

## The artifact

```
apps/ml/models/scamclf-v1.joblib
```

A dict of stock scikit-learn estimators — vectoriser, scaler, classifier —
plus the threshold, the metrics and the training metadata. Stock classes only,
deliberately: unpickling restores classes by import path, so a custom
transformer would have to be importable inside the worker image and would drag
this package into production.

```bash
make -C apps/ml inspect     # threshold, metrics, corpora, trained-at
uv run trustlens-ml predict --title "iPhone 13" --description "advance payment only"
```

Loading checks the format version and the feature order. A reordered feature
vector does not raise on its own — it silently scores the wrong columns — so it
is compared explicitly.

The worker reads the threshold **from the artifact** by default;
`CLASSIFIER_THRESHOLD` overrides it only when deliberately set, because the
stored value was chosen against a curve and an env var was not.

---

## Model and data licences (P7-08)

Everything here is usable for an academic FYP. The face-recognition weights
elsewhere in the project are the item that needs stating in the report.

| Asset                                     | Licence                          | Commercial use       |
| ----------------------------------------- | -------------------------------- | -------------------- |
| EMSCAD fake job postings                  | CC0-1.0 (public domain)          | Yes                  |
| DIFrauD                                   | MIT                              | Yes                  |
| scikit-learn, numpy, scipy                | BSD-3-Clause                     | Yes                  |
| DistilBERT (`distilbert-base-uncased`)    | Apache-2.0                       | Yes, if P7-04 is run |
| **InsightFace `buffalo_s`**               | **Non-commercial research only** | **No**               |
| **DeepFace / ArcFace pretrained weights** | **Non-commercial research only** | **No**               |

The last two rows are the constraint worth a paragraph in the limitations
chapter. Academic FYP use is exactly what those licences permit, so the project
is compliant as it stands — but TrustLens could not be commercialised on those
weights without either a commercial licence or retraining a face model from
permissively-licensed data. Stating that plainly reads as maturity; discovering
it after a launch does not.

Nothing in this package carries a non-commercial licence. The classifier is
trained from scratch on CC0 and MIT data, so the model itself is unencumbered.

---

## Where the report's figures come from

```
apps/ml/reports/scamclf-v1-metrics.json     every number, machine-readable
apps/ml/reports/figures/pr_curve_*.png      precision-recall, with the chance line
apps/ml/reports/figures/roc_curve_*.png     ROC
apps/ml/reports/figures/confusion_*.png     confusion at the chosen threshold
```

The PR curve is drawn with the chance line marked. On a 7%-positive corpus a
precision-recall curve looks far better than it is without it.

`reports/` is gitignored — regenerate with `make -C apps/ml report`, which runs
fetch, train and compare in order from a clean checkout.

---

## Status against Phase 7

| Task                           | State                                                      |
| ------------------------------ | ---------------------------------------------------------- |
| P7-01 training package         | done                                                       |
| P7-02 datasets                 | proxies done (CC0 + MIT); **in-domain corpus outstanding** |
| P7-03 TF-IDF + LogReg baseline | done, trained, exported                                    |
| P7-04 DistilBERT fine-tune     | script written; **not run** — needs Colab GPU              |
| P7-05 evaluation               | done, plus a cross-corpus test the plan did not ask for    |
| P7-06 wired behind the port    | done; `USE_FAKE_AI=false` loads it                         |
| P7-07 this README              | done                                                       |
| P7-08 licence note             | done, above                                                |
