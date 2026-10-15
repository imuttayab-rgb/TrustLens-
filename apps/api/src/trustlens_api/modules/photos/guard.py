"""Bounded, CPU-only photo fingerprints. No model, API key or network lookup.

Version 1 recognises exact files, recompression, resizing, mirrors and a bounded
set of crops/plain screenshot borders. A visual match is NOT proof of ownership.
Fingerprints are private; clients never receive another account's identifiers.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import imagehash
from PIL import Image, ImageChops, ImageOps, ImageStat

MAX_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
VERSION = 1


@dataclass(frozen=True)
class PreparedPhoto:
    jpeg: bytes
    thumbnail: bytes
    width: int
    height: int
    fingerprint: dict[str, Any]
    bands: list[str]
    digests: list[str]
    legacy_dhash: bytes


def _jpeg(img: Image.Image, quality: int) -> bytes:
    out = BytesIO()
    img.save(out, format="JPEG", quality=quality)
    return out.getvalue()


def _trim_plain_border(img: Image.Image) -> Image.Image:
    # Conservative: only a nearly uniform outer frame is removed. Arbitrary
    # screenshot chrome/crops are deliberately not claimed as fully covered.
    pixels = [
        img.getpixel(p)
        for p in [(0, 0), (img.width - 1, 0), (0, img.height - 1), (img.width - 1, img.height - 1)]
    ]
    if any(max(abs(a - b) for a, b in zip(pixels[0], p)) > 12 for p in pixels[1:]):
        return img
    diff = ImageChops.difference(img, Image.new("RGB", img.size, pixels[0]))
    mask = diff.convert("L").point(lambda x: 255 if x > 18 else 0)
    box = mask.getbbox()
    if box and (box[2] - box[0]) * (box[3] - box[1]) >= img.width * img.height * 0.3:
        return img.crop(box)
    return img


def _views(img: Image.Image) -> list[Image.Image]:
    small = img.copy()
    small.thumbnail((384, 384))
    bases = [small]
    trimmed = _trim_plain_border(small)
    if trimmed.size != small.size:
        bases.append(trimmed)
    views = []
    for base in bases:
        views.append(base)
        for fraction in (0.08, 0.16, 0.25):
            x, y = round(base.width * fraction), round(base.height * fraction)
            views.append(base.crop((x, y, base.width - x, base.height - y)))
    return views


def fingerprint(img: Image.Image, raw: bytes, jpeg: bytes) -> tuple[dict, list[str], list[str]]:
    records = []
    bands: set[str] = set()
    for view in _views(img):
        for mirrored in (False, True):
            current = ImageOps.mirror(view) if mirrored else view
            hash_value = str(imagehash.dhash(current, hash_size=16))
            sample = current.resize((24, 24), Image.Resampling.LANCZOS)
            records.append(
                {
                    "hash": hash_value,
                    "sample": base64.b64encode(sample.tobytes()).decode(),
                    "texture": round(ImageStat.Stat(sample.convert("L")).stddev[0], 2),
                }
            )
            for index in range(16):
                chunk = hash_value[index * 4 : index * 4 + 4]
                if 3 <= int(chunk, 16).bit_count() <= 13:
                    bands.add(f"{index}:{chunk}")
    pixel_hash = hashlib.sha256()
    pixel_hash.update(f"RGB:{img.width}:{img.height}:".encode())
    # Avoid allocating an additional full-resolution .tobytes() buffer.
    for y in range(0, img.height, 64):
        pixel_hash.update(img.crop((0, y, img.width, min(y + 64, img.height))).tobytes())
    digests = sorted(
        {hashlib.sha256(raw).hexdigest(), hashlib.sha256(jpeg).hexdigest(), pixel_hash.hexdigest()}
    )
    return {"version": VERSION, "views": records}, sorted(bands), digests


def prepare_photo(raw: bytes) -> PreparedPhoto:
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Use a photo of 10 MB or smaller.")
    with Image.open(BytesIO(raw)) as opened:
        if opened.format not in {"JPEG", "PNG", "WEBP"}:
            raise ValueError("Use a JPEG, PNG or WebP photo.")
        if opened.width * opened.height > MAX_PIXELS:
            raise ValueError("For this local setup, resize the photo to 20 megapixels or less.")
        if getattr(opened, "n_frames", 1) != 1:
            raise ValueError("Use a still photo, not an animated image.")
        # Decode JPEG at a reduced resolution to reduce local peak memory.
        opened.draft("RGB", (2048, 2048))
        oriented = ImageOps.exif_transpose(opened)
        oriented.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        img = oriented.convert("RGB")
    jpeg = _jpeg(img, 90)
    fp, bands, digests = fingerprint(img, raw, jpeg)
    thumb = img.copy()
    thumb.thumbnail((400, 400))
    return PreparedPhoto(
        jpeg,
        _jpeg(thumb, 85),
        img.width,
        img.height,
        fp,
        bands,
        digests,
        imagehash.dhash(img, hash_size=8).hash.tobytes(),
    )


def visually_matches(left: dict, right: dict) -> bool:
    """Conservative photo-content comparison, not object/model recognition."""
    if left.get("version") != VERSION or right.get("version") != VERSION:
        return False
    for a in left["views"]:
        if a["texture"] < 18:
            continue  # featureless/stock backgrounds are not near-copy evidence
        for b in right["views"]:
            if b["texture"] < 18 or (int(a["hash"], 16) ^ int(b["hash"], 16)).bit_count() > 12:
                continue
            ia = Image.frombytes("RGB", (24, 24), base64.b64decode(a["sample"]))
            ib = Image.frombytes("RGB", (24, 24), base64.b64decode(b["sample"]))
            # Hash similarity alone is insufficient: enforce spatial colour
            # agreement to avoid equating two photos of the same phone model.
            diff = ImageStat.Stat(ImageChops.difference(ia, ib))
            if max(diff.mean) <= 7 and max(diff.rms) <= 12:
                return True
    return False
