"""Synthetic test pattern only; no human photo or real national ID is used."""
from __future__ import annotations

import cv2
import numpy as np

from trustlens_worker.jobs.hold_card import compare_card_frames


def synthetic_card(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    card = np.full((480, 760, 3), 225, dtype=np.uint8)
    cv2.rectangle(card, (5, 5), (754, 474), (35, 35, 35), 4)
    # Deterministic abstract shapes make an ORB texture without imitating CNIC
    # content, printing an identity number, or representing a real face.
    for _ in range(140):
        x, y = int(rng.integers(15, 740)), int(rng.integers(15, 465))
        radius = int(rng.integers(2, 9))
        color = int(rng.integers(10, 150))
        cv2.circle(card, (x, y), radius, (color, color, color), -1)
    return card


def jpg(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode('.jpg', image)
    assert ok
    return encoded.tobytes()


def test_same_synthetic_card_visible_in_holding_frame() -> None:
    card = synthetic_card(7)
    scene = np.full((720, 1280, 3), 190, dtype=np.uint8)
    scene[280:520, 80:460] = cv2.resize(card, (380, 240))
    evidence = compare_card_frames(jpg(card), jpg(scene))
    assert evidence.card_found
    assert evidence.inliers >= 9


def test_unrelated_synthetic_card_cannot_match() -> None:
    card = synthetic_card(7)
    scene = np.full((720, 1280, 3), 190, dtype=np.uint8)
    scene[280:520, 80:460] = cv2.resize(synthetic_card(101), (380, 240))
    assert not compare_card_frames(jpg(card), jpg(scene)).card_found


def test_unreadable_upload_is_inconclusive() -> None:
    assert not compare_card_frames(b'not-an-image', jpg(synthetic_card(7))).card_found
