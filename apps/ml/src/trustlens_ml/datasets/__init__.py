"""Corpus fetching, loading and normalisation."""

from trustlens_ml.datasets.loaders import fetch, fetch_all, load
from trustlens_ml.datasets.schema import CORPORA, CorpusSpec, Example, Provenance

__all__ = [
    "CORPORA",
    "CorpusSpec",
    "Example",
    "Provenance",
    "fetch",
    "fetch_all",
    "load",
]
