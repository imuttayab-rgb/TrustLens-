"""Fetching corpora, and normalising each one into `Example`.

Downloads are cached on disk and skipped if the file is already there, so
training is repeatable offline once the data has been pulled. Nothing here
writes into git: `apps/ml/datasets/.gitignore` blocks everything but the
manifests, which is the same rule the CNIC benchmark data follows.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from trustlens.shared.logging import get_logger
from trustlens_ml.datasets.schema import (
    CORPORA,
    CorpusSpec,
    Example,
    Provenance,
)

log = get_logger(__name__)

DATA_ROOT = Path(__file__).resolve().parents[3] / "datasets"

# EMSCAD carries whole job adverts in one cell; the csv module's default limit
# is smaller than the longest of them and raises rather than truncating.
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))


def fetch(spec: CorpusSpec, *, root: Path | None = None, force: bool = False) -> list[Path]:
    """Download a corpus if it is not already present. Returns local paths."""
    import httpx

    root = root or DATA_ROOT
    paths: list[Path] = []
    for url, relative in spec.files:
        target = root / relative
        paths.append(target)
        if target.exists() and not force:
            log.info("corpus_cached", corpus=spec.key, file=relative)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("corpus_downloading", corpus=spec.key, url=url)
        with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
            response.raise_for_status()
            with target.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        log.info("corpus_downloaded", corpus=spec.key, bytes=target.stat().st_size)
    return paths


def _clean(value: str | None) -> str:
    """EMSCAD writes missing cells as the literal string 'nan'."""
    if not value:
        return ""
    text = value.strip()
    return "" if text.lower() in {"nan", "none", "null"} else text


def load_emscad(root: Path | None = None) -> list[Example]:
    path = (root or DATA_ROOT) / "emscad" / "fake_job_postings.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing - run `trustlens-ml fetch` first")

    examples: list[Example] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            # company_profile + description + requirements is the advert as a
            # reader sees it. Benefits is excluded: it is boilerplate in both
            # classes and adds vocabulary without signal.
            body = " ".join(
                _clean(row.get(field))
                for field in ("company_profile", "description", "requirements")
            ).strip()
            title = _clean(row.get("title"))
            if not body and not title:
                continue
            examples.append(
                Example(
                    title=title,
                    description=body,
                    label=int(_clean(row.get("fraudulent")) or 0),
                    corpus="emscad",
                    provenance=Provenance.PROXY,
                    category=_clean(row.get("industry")) or None,
                )
            )
    return examples


def load_difraud(root: Path | None = None) -> list[Example]:
    base = (root or DATA_ROOT) / "difraud"
    if not base.exists():
        raise FileNotFoundError(f"{base} missing - run `trustlens-ml fetch` first")

    examples: list[Example] = []
    for path in sorted(base.glob("*.jsonl")):
        domain = path.stem.rsplit("_", 1)[0]
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                text = _clean(row.get("text"))
                if not text:
                    continue
                label = row.get("label")
                if label is None:
                    continue
                examples.append(
                    Example(
                        # These corpora are bodies without titles. An empty
                        # title is honest; inventing one from the first line
                        # would feed the title features something no real
                        # listing would contain.
                        title="",
                        description=text,
                        label=int(label),
                        corpus=f"difraud:{domain}",
                        provenance=Provenance.PROXY,
                    )
                )
    return examples


def load_local_ads(root: Path | None = None) -> list[Example]:
    """The hand-labelled Pakistani ads (P7-02).

    Returns an empty list when the file does not exist, rather than raising:
    the rest of the pipeline must run without it, and every report this package
    writes states plainly when the in-domain corpus was absent.
    """
    base = (root or DATA_ROOT) / "local_ads"
    path = base / "local_ads.csv"
    if not path.exists():
        # The synthetic probe set is a fallback, never a silent substitute:
        # every caller is told which file it got, and `render` in compare.py
        # repeats that sixteen author-written rows cannot measure accuracy.
        example = base / "local_ads.example.csv"
        if example.exists():
            log.warning("local_ads_missing_using_synthetic_probe", path=str(example))
            path = example
        else:
            log.warning("local_ads_missing", path=str(path))
            return []

    examples: list[Example] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            title = _clean(row.get("title"))
            description = _clean(row.get("description"))
            if not title and not description:
                continue
            price_raw = _clean(row.get("price"))
            examples.append(
                Example(
                    title=title,
                    description=description,
                    label=int(_clean(row.get("label")) or 0),
                    corpus="local_ads",
                    provenance=Provenance.IN_DOMAIN,
                    price=float(price_raw) if price_raw else None,
                    category=_clean(row.get("category")) or None,
                )
            )
    return examples


LOADERS = {
    "emscad": load_emscad,
    "difraud": load_difraud,
    "local_ads": load_local_ads,
}


def load(keys: list[str], *, root: Path | None = None) -> list[Example]:
    examples: list[Example] = []
    for key in keys:
        if key not in LOADERS:
            raise KeyError(f"unknown corpus {key!r}; known: {sorted(LOADERS)}")
        loaded = LOADERS[key](root)
        log.info(
            "corpus_loaded",
            corpus=key,
            rows=len(loaded),
            positives=sum(e.label for e in loaded),
        )
        examples.extend(loaded)
    return examples


def fetch_all(*, root: Path | None = None, force: bool = False) -> None:
    for spec in CORPORA.values():
        if not spec.files:
            log.info("corpus_not_downloadable", corpus=spec.key, note=spec.notes)
            continue
        fetch(spec, root=root, force=force)


__all__ = [
    "DATA_ROOT",
    "LOADERS",
    "fetch",
    "fetch_all",
    "load",
    "load_difraud",
    "load_emscad",
    "load_local_ads",
]
