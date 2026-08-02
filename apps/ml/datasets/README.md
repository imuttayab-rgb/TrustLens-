# Benchmark datasets (P1-01, P1-06)

The benchmarks need real images. Collecting them is a **human task** — it cannot
be automated, and it is the gate that unblocks Phase 1.

> ⚠️ **Never commit real CNIC or selfie images.** `.gitignore` in this directory
> blocks everything except the example manifests. A CNIC is sensitive personal
> data under Pakistan's data protection regime, and anything reaching git
> history is effectively permanent — deleting the file later does not remove it.

---

## Consent

Before photographing anyone's CNIC, tell them plainly:

- what you are testing and why,
- that the image stays on your machine and is never uploaded or committed,
- that you will delete it when the benchmark is finished,
- that they can withdraw at any time.

Keep a note of who agreed. One line per person is enough. This is both the right
thing to do and a paragraph in the report's ethics section.

---

## CNIC set (P1-01) — target 10–15 images

Accuracy on clean scans tells you nothing. What matters is how the system
behaves on the photos people actually upload, so deliberately include the bad
cases:

| `condition`  | What it means                                  | How many |
| ------------ | ---------------------------------------------- | -------- |
| `good_light` | Flat, well lit, in focus, card fills the frame | 4–5      |
| `low_light`  | Indoors at night, dim                          | 2        |
| `angled`     | Photographed at 20–40° rather than flat        | 2        |
| `glare`      | Flash or window reflection across the card     | 2        |
| `blurry`     | Slight camera shake                            | 2        |
| `screenshot` | A photo of a CNIC shown on a screen            | 1–2      |

That last one matters — it is the cheapest forgery attempt, and the system
should not treat it as a clean read.

Put the images in `apps/ml/datasets/cnic/` and record ground truth in
`cnic_manifest.csv`, copying the header from `cnic_manifest.example.csv`.

Type the values **exactly as printed on the card**. The manifest is the
reference the benchmark scores against, so a typo here shows up as a model
error.

Leave a column blank when the field genuinely is not readable — blank means
"not scored", not "expected empty".

```bash
uv run python apps/ml/bench/ocr_bench.py \
  --manifest apps/ml/datasets/cnic_manifest.csv \
  --images-dir apps/ml/datasets/cnic \
  --out apps/ml/results/ocr_baseline.json
```

Run it **before** tuning `preprocessing.py`, save the JSON, then run it again
after tuning. Both numbers go in the report — an improvement is only meaningful
against a baseline.

**P1-03 gate:** CNIC-number accuracy ≥ 90% on the `good_light` subset.

---

## Face set (P1-06) — target 10 matching + 10 non-matching pairs

Each row pairs a **document photo** (the face cropped from a CNIC) with a
**selfie**, labelled by whether they are the same person.

- **10 matching pairs** — the same person's CNIC photo and a fresh selfie.
  Include hard-but-genuine cases: an old CNIC photo, a beard grown or shaved,
  glasses, a headscarf. These are exactly where honest sellers get wrongly
  rejected.
- **10 non-matching pairs** — one person's CNIC against a different person's
  selfie. Include a few same-gender, similar-age pairs; matching a man's photo
  against a woman's is a test the model cannot fail and therefore proves little.

Put the images in `apps/ml/datasets/faces/` and fill in `face_manifest.csv`.

```bash
uv run python apps/ml/bench/face_bench.py \
  --manifest apps/ml/datasets/face_manifest.csv \
  --images-dir apps/ml/datasets/faces \
  --out apps/ml/results/face_baseline.json
```

The sweep prints a false-accept and false-reject rate at every threshold and
recommends one. Put the recommended value in `FACE_MATCH_THRESHOLD` and record
the trade-off in the report.

---

## After Phase 1

Delete the images once the numbers are recorded. The JSON reports in
`apps/ml/results/` contain the measurements and no personal data, so they are
what you keep.
