"""Tests for the identity verification decision table (P1-05).

`_decide` is a pure function of its command - no I/O, no clock - so it is
tested directly. The collaborators are never touched on this path.

The property that matters here: **an unreadable upload must not be recorded as
a failure.** A FAILED identity signal applies a hard cap in the scoring policy,
and a seller cannot appeal against a blurry photograph. Ambiguity belongs in a
review queue, not in a penalty.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pytest

from trustlens.core.application.use_cases.verification.identity import (
    FinalizeIdentityCommand,
    FinalizeIdentityVerification,
)
from trustlens.core.domain.enums import VerificationStatus

THRESHOLD = 0.62
REVIEW_LOWER = 0.45

#: (command, duplicate_count) -> (decision, needs_review, reason)
Decider = Callable[[FinalizeIdentityCommand, int], tuple[VerificationStatus, bool, str]]


def make_command(**overrides: Any) -> FinalizeIdentityCommand:
    defaults: dict[str, Any] = {
        "verification_id": cast(Any, "00000000-0000-0000-0000-000000000001"),
        "ocr_confidence": 0.91,
        "face_similarity": 0.80,
        "face_distance": 0.30,
        "threshold": THRESHOLD,
        "review_lower_bound": REVIEW_LOWER,
        "liveness_passed": True,
        "cnic_hash": None,
        "document_expired": False,
        "engine": "deepface",
        "engine_version": "ArcFace",
        "raw": {},
        "cnic_needs_review": False,
        "cnic_check_failures": (),
    }
    return FinalizeIdentityCommand(**{**defaults, **overrides})


@pytest.fixture
def decide() -> Decider:
    """`_decide` needs no collaborators, so none are constructed."""
    use_case = FinalizeIdentityVerification(
        uow=cast(Any, None), queue=cast(Any, None), clock=cast(Any, None), ids=cast(Any, None)
    )
    return use_case._decide


class TestUnreadableDocuments:
    def test_missing_ocr_goes_to_review_not_failure(self, decide: Decider) -> None:
        decision, needs_review, reason = decide(make_command(ocr_confidence=None), 0)
        assert decision is VerificationStatus.PENDING
        assert needs_review
        assert "manual review" in reason.lower()

    def test_missing_face_similarity_goes_to_review(self, decide: Decider) -> None:
        decision, needs_review, _ = decide(make_command(face_similarity=None), 0)
        assert decision is VerificationStatus.PENDING
        assert needs_review


class TestHardRejections:
    def test_expired_document_is_rejected_without_review(self, decide: Decider) -> None:
        """Expiry is an unambiguous, seller-fixable fact - no human needed."""
        decision, needs_review, reason = decide(make_command(document_expired=True), 0)
        assert decision is VerificationStatus.REJECTED
        assert not needs_review
        assert "expired" in reason.lower()

    def test_reliable_expiry_outranks_an_unreadable_face(self, decide: Decider) -> None:
        """A clearly expired card cannot become valid in review; resubmit instead."""
        decision, needs_review, reason = decide(
            make_command(document_expired=True, face_similarity=None), 0
        )
        assert decision is VerificationStatus.REJECTED
        assert not needs_review
        assert "expired" in reason.lower()

    def test_duplicate_cnic_is_rejected_and_reviewed(self, decide: Decider) -> None:
        # One prior owner is already a duplicate for this new account.
        decision, needs_review, _ = decide(make_command(), 1)
        assert decision is VerificationStatus.REJECTED
        assert needs_review

    def test_clear_face_mismatch_is_rejected(self, decide: Decider) -> None:
        decision, needs_review, reason = decide(make_command(face_similarity=0.10), 0)
        assert decision is VerificationStatus.REJECTED
        assert not needs_review
        assert "does not match" in reason.lower()


class TestCnicCrossChecks:
    def test_self_contradictory_card_goes_to_review(self, decide: Decider) -> None:
        """Gender digit disagrees with the printed field - OCR error or forgery."""
        decision, needs_review, _ = decide(
            make_command(cnic_needs_review=True, cnic_check_failures=("CNIC_GENDER_MISMATCH",)),
            0,
        )
        assert decision is VerificationStatus.PENDING
        assert needs_review

    def test_cross_check_review_outranks_a_passing_face_match(self, decide: Decider) -> None:
        """A strong face match must not wave through a card that contradicts itself."""
        decision, _, _ = decide(make_command(face_similarity=0.99, cnic_needs_review=True), 0)
        assert decision is VerificationStatus.PENDING

    def test_expiry_still_outranks_cross_checks(self, decide: Decider) -> None:
        decision, _, reason = decide(make_command(document_expired=True, cnic_needs_review=True), 0)
        assert decision is VerificationStatus.REJECTED
        assert "expired" in reason.lower()


class TestSuccessAndBorderline:
    def test_clean_match_verifies(self, decide: Decider) -> None:
        decision, needs_review, _ = decide(make_command(face_similarity=0.80), 0)
        assert decision is VerificationStatus.VERIFIED
        assert not needs_review

    def test_similarity_exactly_at_threshold_verifies(self, decide: Decider) -> None:
        decision, _, _ = decide(make_command(face_similarity=THRESHOLD), 0)
        assert decision is VerificationStatus.VERIFIED

    def test_borderline_similarity_goes_to_review(self, decide: Decider) -> None:
        """Face matching has known demographic error-rate disparities; a false
        rejection costs a real person their ability to trade."""
        decision, needs_review, _ = decide(make_command(face_similarity=0.50), 0)
        assert decision is VerificationStatus.PENDING
        assert needs_review

    def test_card_beside_face_is_reviewed_even_with_strong_matches(self, decide: Decider) -> None:
        decision, needs_review, reason = decide(
            make_command(
                hold_review_required=True,
                hold_card_found=True,
                holder_face_similarity=0.91,
                face_similarity=0.99,
            ), 0
        )
        assert decision is VerificationStatus.PENDING
        assert needs_review
        assert "human review" in reason

    def test_missing_hold_card_is_review_not_automatic_fraud(self, decide: Decider) -> None:
        command = make_command(hold_review_required=True, hold_card_found=False)
        decision, needs_review, _ = decide(command, 0)
        assert decision is VerificationStatus.PENDING
        assert needs_review
        assert "could not be confirmed" in FinalizeIdentityVerification._review_reason(command, 0)

    def test_expired_id_remains_rejected_with_hold_card(self, decide: Decider) -> None:
        decision, _, _ = decide(
            make_command(hold_review_required=True, document_expired=True), 0
        )
        assert decision is VerificationStatus.REJECTED


class TestReviewReason:
    @pytest.mark.parametrize(
        ("command_kwargs", "duplicates", "expected"),
        [
            ({}, 1, "Duplicate CNIC across accounts"),
            ({"ocr_confidence": None}, 0, "Documents could not be read automatically"),
            (
                {"cnic_check_failures": ("CNIC_GENDER_MISMATCH",)},
                0,
                "CNIC cross-check failed: CNIC_GENDER_MISMATCH",
            ),
            ({}, 0, "Borderline face-match similarity"),
        ],
    )
    def test_reason_describes_why_a_human_was_called(
        self, command_kwargs: dict[str, Any], duplicates: int, expected: str
    ) -> None:
        reason = FinalizeIdentityVerification._review_reason(
            make_command(**command_kwargs), duplicates
        )
        assert reason == expected
