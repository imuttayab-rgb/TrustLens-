"""OpenCV preprocessing for CNIC images.

OCR accuracy on phone photos of ID cards is dominated by preprocessing, not by
the OCR engine. A skewed, glared, low-contrast photo will defeat EasyOCR no
matter how good the model is - so this pipeline runs before every extraction.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def decode_image(data: bytes) -> Any:
    import cv2

    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("image could not be decoded")
    return image


def deskew(image: Any) -> Any:
    """Straighten a tilted card using the dominant text angle."""
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    inverted = cv2.bitwise_not(gray)
    threshold = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(threshold > 0))
    if coords.size == 0:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    # Ignore tiny angles: rotating by half a degree costs sharpness for
    # nothing, and interpolation blur hurts OCR more than the tilt does.
    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def enhance(image: Any) -> Any:
    """Denoise and normalise contrast.

    CLAHE rather than global equalisation: an ID photographed under a lamp has
    a bright patch and a dark patch, and global equalisation makes both worse.
    """
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def quality_score(image: Any) -> float:
    """Blur/exposure gate, 0..1.

    Rejecting a bad photo up front and asking for a retake is far better UX
    than running the full pipeline and reporting an unexplainable failure.
    """
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    sharpness = min(1.0, cv2.Laplacian(gray, cv2.CV_64F).var() / 500.0)
    brightness = float(np.mean(gray)) / 255.0
    exposure = 1.0 - abs(brightness - 0.5) * 2
    # round() over numpy scalars widens to Any; the port promises a float.
    return float(round(max(0.0, min(1.0, 0.7 * sharpness + 0.3 * exposure)), 3))


def prepare_for_ocr(data: bytes) -> tuple[Any, float]:
    image = decode_image(data)
    score = quality_score(image)
    return enhance(deskew(image)), score


__all__ = ["decode_image", "deskew", "enhance", "prepare_for_ocr", "quality_score"]
