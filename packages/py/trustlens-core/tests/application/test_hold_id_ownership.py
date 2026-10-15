"""Ensure four-file validation prevents cross-account evidence reference (IDOR)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID

import pytest

from trustlens.core.application.use_cases.verification.identity import (
    SubmitIdentityCommand,
    SubmitIdentityDocuments,
)
from trustlens.core.domain.enums import FilePurpose
from trustlens.core.domain.errors import ValidationError


@pytest.mark.asyncio
async def test_hold_card_from_other_user_is_not_accepted() -> None:
    owner = UUID('00000000-0000-0000-0000-000000000001')
    other = UUID('00000000-0000-0000-0000-000000000002')
    files = {
        UUID(int=11): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.CNIC_FRONT),
        UUID(int=12): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.CNIC_BACK),
        UUID(int=13): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.SELFIE),
        UUID(int=14): SimpleNamespace(owner_user_id=other, purpose=FilePurpose.HOLD_ID),
    }

    class Files:
        async def get(self, file_id: UUID) -> Any:
            return files.get(file_id)

    use_case = SubmitIdentityDocuments(
        uow=cast(Any, SimpleNamespace(files=Files())),
        queue=cast(Any, None), clock=cast(Any, None), ids=cast(Any, None),
    )
    with pytest.raises(ValidationError):
        await use_case._validate_files(
            SubmitIdentityCommand(owner, UUID(int=11), UUID(int=12), UUID(int=13), UUID(int=14)),
            owner,
        )


@pytest.mark.asyncio
async def test_hold_card_requires_correct_purpose() -> None:
    owner = UUID(int=1)
    files = {
        UUID(int=11): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.CNIC_FRONT),
        UUID(int=12): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.CNIC_BACK),
        UUID(int=13): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.SELFIE),
        UUID(int=14): SimpleNamespace(owner_user_id=owner, purpose=FilePurpose.LISTING_IMAGE),
    }

    class Files:
        async def get(self, file_id: UUID) -> Any:
            return files.get(file_id)

    use_case = SubmitIdentityDocuments(
        uow=cast(Any, SimpleNamespace(files=Files())),
        queue=cast(Any, None), clock=cast(Any, None), ids=cast(Any, None),
    )
    with pytest.raises(ValidationError):
        await use_case._validate_files(
            SubmitIdentityCommand(owner, UUID(int=11), UUID(int=12), UUID(int=13), UUID(int=14)),
            owner,
        )
