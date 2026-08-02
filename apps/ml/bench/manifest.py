"""Shared manifest loading for the Phase 1 benchmarks.

A manifest is a CSV of ground truth: one row per test image, with the values a
human read off the card. Benchmarks compare model output against it.

The images themselves never enter git (see `apps/ml/datasets/.gitignore`). A
CNIC is sensitive personal data under Pakistan's data protection regime, and
anything committed to a repository is effectively permanent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


def _parse_date(raw: str | None) -> date | None:
    if not raw or not raw.strip():
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date format: {raw!r}")


def _parse_bool(raw: str | None) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "same"}


@dataclass(frozen=True, slots=True)
class CnicSample:
    """One CNIC image plus the fields a human read off it."""

    image: Path
    condition: str
    cnic_number: str | None = None
    full_name: str | None = None
    father_name: str | None = None
    date_of_birth: date | None = None
    expiry_date: date | None = None
    gender: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FacePair:
    """A document photo and a selfie, labelled with whether they are the same person."""

    document_image: Path
    selfie_image: Path
    same_person: bool
    condition: str = ""


def _resolve(images_dir: Path, value: str) -> Path:
    path = (images_dir / value.strip()).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Image listed in manifest does not exist: {path}")
    return path


def load_cnic_manifest(manifest: Path, images_dir: Path) -> list[CnicSample]:
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    return [
        CnicSample(
            image=_resolve(images_dir, row["image"]),
            condition=(row.get("condition") or "unspecified").strip(),
            cnic_number=(row.get("cnic_number") or "").strip() or None,
            full_name=(row.get("full_name") or "").strip() or None,
            father_name=(row.get("father_name") or "").strip() or None,
            date_of_birth=_parse_date(row.get("date_of_birth")),
            expiry_date=_parse_date(row.get("expiry_date")),
            gender=((row.get("gender") or "").strip().upper() or None),
        )
        for row in rows
    ]


def load_face_manifest(manifest: Path, images_dir: Path) -> list[FacePair]:
    with manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    return [
        FacePair(
            document_image=_resolve(images_dir, row["document_image"]),
            selfie_image=_resolve(images_dir, row["selfie_image"]),
            same_person=_parse_bool(row.get("same_person")),
            condition=(row.get("condition") or "").strip(),
        )
        for row in rows
    ]


__all__ = ["CnicSample", "FacePair", "load_cnic_manifest", "load_face_manifest"]
