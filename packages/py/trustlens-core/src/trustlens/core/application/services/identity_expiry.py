"""When has a seller's verified ID card passed its printed expiry date?

Only evidence from a REAL OCR engine counts. Fake OCR invents an expiry from
image bytes and the demo seed has none, so neither may ever revoke a seller.
In real-OCR mode the worker stores an expiry only when it was read reliably
(birth, issue and expiry all present, confident read, sides consistent), so a
stored real-OCR expiry is safe to enforce without a human.

Only documents linked to the seller's LATEST verification are considered: an
expired card from an older, superseded submission must not revoke a seller
who has since verified with a valid card.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from trustlens.core.domain.entities import IdentityDocument, IdentityVerification

#: OCR engine names whose dates are NOT real readings of a physical card.
SIMULATED_OCR_ENGINES = frozenset({"fake", "demo"})


def is_real_ocr_engine(engine: str | None) -> bool:
    return bool(engine) and engine not in SIMULATED_OCR_ENGINES


def real_ocr_expiry(
    verification: IdentityVerification | None, documents: Iterable[IdentityDocument]
) -> date | None:
    """Earliest real-OCR expiry on the CNIC sides linked to `verification`."""
    if verification is None:
        return None
    linked = {verification.front_document_id, verification.back_document_id} - {None}
    dates = [
        d.fields.expiry_date
        for d in documents
        if d.id in linked and is_real_ocr_engine(d.ocr_engine) and d.fields.expiry_date
    ]
    return min(dates) if dates else None


def lapsed_expiry(
    verification: IdentityVerification | None,
    documents: Iterable[IdentityDocument],
    today: date,
) -> date | None:
    """The real-OCR expiry if it is strictly before `today`, else None.

    A card is valid THROUGH its expiry date, matching cnic_validation.
    """
    expiry = real_ocr_expiry(verification, documents)
    return expiry if expiry is not None and expiry < today else None


__all__ = ["SIMULATED_OCR_ENGINES", "is_real_ocr_engine", "lapsed_expiry", "real_ocr_expiry"]
