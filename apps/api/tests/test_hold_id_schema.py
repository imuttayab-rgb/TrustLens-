"""Four-image pilot request/retention tests; no private data or database required."""
from uuid import UUID

from trustlens.core.domain.enums import FilePurpose
from trustlens_api.api.v1.schemas.verification import SubmitIdentityRequest, UploadIntentRequest


def test_legacy_three_image_request_still_valid() -> None:
    body = SubmitIdentityRequest.model_validate({
        "cnicFrontFileId": "00000000-0000-0000-0000-000000000001",
        "cnicBackFileId": "00000000-0000-0000-0000-000000000002",
        "selfieFileId": "00000000-0000-0000-0000-000000000003",
        "biometricConsent": True,
    })
    assert body.hold_id_file_id is None


def test_optional_hold_image_can_be_submitted_under_new_pilot() -> None:
    body = SubmitIdentityRequest.model_validate({
        "cnicFrontFileId": "00000000-0000-0000-0000-000000000001",
        "cnicBackFileId": "00000000-0000-0000-0000-000000000002",
        "selfieFileId": "00000000-0000-0000-0000-000000000003",
        "holdIdFileId": "00000000-0000-0000-0000-000000000004",
        "biometricConsent": True,
    })
    assert body.hold_id_file_id == UUID("00000000-0000-0000-0000-000000000004")
    assert FilePurpose.HOLD_ID.is_sensitive
    intent = UploadIntentRequest(
        purpose="HOLD_ID", content_type="image/jpeg", size_bytes=1000
    )
    assert FilePurpose(intent.purpose) is FilePurpose.HOLD_ID
