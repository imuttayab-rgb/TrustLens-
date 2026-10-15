"""Non-authoritative card-presence evidence for the opt-in hold-ID review pilot.

ORB feature matching checks whether the card's printed visual pattern from the
separate front scan also appears in the holding-card frame. This does NOT prove
that the plastic card is genuine, that the person is physically present, or that
the camera is not virtual. False negatives (blur/glare/small card) go to human
review; this check never auto-rejects or auto-verifies a seller.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HoldCardEvidence:
    card_found: bool
    good_matches: int
    inliers: int


def compare_card_frames(front_image: bytes, hold_image: bytes) -> HoldCardEvidence:
    """Match local features after bounded resizing; avoid persisting any pixels."""
    import cv2
    import numpy as np

    def decode(data: bytes):
        decoded = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if decoded is None:
            return None
        height, width = decoded.shape[:2]
        if height < 120 or width < 120:
            return None
        scale = min(1.0, 1400 / max(height, width))
        if scale < 1:
            decoded = cv2.resize(decoded, None, fx=scale, fy=scale)
        return cv2.equalizeHist(decoded)

    front = decode(front_image)
    hold = decode(hold_image)
    if front is None or hold is None:
        return HoldCardEvidence(False, 0, 0)

    orb = cv2.ORB_create(nfeatures=1500)
    front_points, front_descriptors = orb.detectAndCompute(front, None)
    hold_points, hold_descriptors = orb.detectAndCompute(hold, None)
    if front_descriptors is None or hold_descriptors is None:
        return HoldCardEvidence(False, 0, 0)
    if len(front_points) < 12 or len(hold_points) < 12:
        return HoldCardEvidence(False, 0, 0)

    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(front_descriptors, hold_descriptors, k=2)
    good = [
        a for pair in matches if len(pair) == 2
        for a, b in [pair] if a.distance < 0.75 * b.distance
    ]
    if len(good) < 12:
        return HoldCardEvidence(False, len(good), 0)

    source = np.float32([front_points[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    target = np.float32([hold_points[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    matrix, mask = cv2.findHomography(source, target, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if matrix is None or inliers < 9:
        return HoldCardEvidence(False, len(good), inliers)
    corners = np.float32([
        [0, 0], [front.shape[1], 0],
        [front.shape[1], front.shape[0]], [0, front.shape[0]],
    ]).reshape(-1, 1, 2)
    polygon = cv2.perspectiveTransform(corners, matrix).reshape(-1, 2)
    scene_height, scene_width = hold.shape[:2]
    area = abs(cv2.contourArea(polygon))
    # Reject a tiny accidental match or a projected card mostly outside frame.
    within = all(
        -0.05 * scene_width <= x <= 1.05 * scene_width
        and -0.05 * scene_height <= y <= 1.05 * scene_height
        for x, y in polygon
    )
    plausible = (
        within and 0.015 * scene_width * scene_height
        <= area <= 0.7 * scene_width * scene_height
    )
    return HoldCardEvidence(bool(plausible), len(good), inliers)


__all__ = ["HoldCardEvidence", "compare_card_frames"]
