"""HMAC response signing (P6-04).

A Trust Score is a claim about a person that money moves on. A marketplace
receiving one through a proxy or a cache it does not control cannot otherwise
tell it apart from a score an attacker wrote - so the signature is the thing
that makes the public API quotable rather than merely readable.

These tests are written from the partner's side: they check what a marketplace
can and cannot prove with the signature we hand them.
"""

from __future__ import annotations

from trustlens.shared.crypto import HmacResponseSigner

SECRET = b"a-shared-secret-for-partner-verification"
OTHER_SECRET = b"a-different-secret-entirely-here-ok-yes"

NOW = 1_786_000_000


def signer(**kwargs: object) -> HmacResponseSigner:
    return HmacResponseSigner(SECRET, "s1", **kwargs)  # type: ignore[arg-type]


class TestSignAndVerify:
    def test_a_partner_can_verify_what_we_sent(self) -> None:
        s = signer()
        body = b'{"score":95}'
        signature = s.sign(body, timestamp=NOW)
        assert s.verify(body, timestamp=NOW, signature=signature)

    def test_a_tampered_score_fails_verification(self) -> None:
        # The whole point: flipping 25 to 95 in transit must be detectable.
        s = signer()
        signature = s.sign(b'{"score":25}', timestamp=NOW)
        assert not s.verify(b'{"score":95}', timestamp=NOW, signature=signature)

    def test_a_signature_from_another_key_fails(self) -> None:
        signature = HmacResponseSigner(OTHER_SECRET, "s1").sign(b'{"score":95}', timestamp=NOW)
        assert not signer().verify(b'{"score":95}', timestamp=NOW, signature=signature)

    def test_the_timestamp_is_inside_the_signed_material(self) -> None:
        # Signing the body alone would let a captured "score: 95" be replayed
        # forever. Re-presenting the same body under a different timestamp must
        # not verify against the original signature.
        s = signer()
        signature = s.sign(b'{"score":95}', timestamp=NOW)
        assert not s.verify(b'{"score":95}', timestamp=NOW + 1, signature=signature)

    def test_the_signature_names_its_format_and_timestamp(self) -> None:
        # `t=<ts>,v1=<hmac>`: the same shape as the webhook signature, so a
        # partner writes one verification routine rather than two.
        signature = signer().sign(b"{}", timestamp=NOW)
        assert signature.startswith(f"t={NOW},v1=")

    def test_garbage_does_not_verify(self) -> None:
        assert not signer().verify(b"{}", timestamp=NOW, signature="nonsense")

    def test_an_empty_signature_does_not_verify(self) -> None:
        assert not signer().verify(b"{}", timestamp=NOW, signature="")


class TestFreshness:
    def test_a_current_response_is_fresh(self) -> None:
        assert signer(max_age_seconds=300).is_fresh(NOW, now=NOW + 10)

    def test_a_stale_response_is_refused(self) -> None:
        # A captured response replayed an hour later is not current, even
        # though its signature is perfectly valid.
        assert not signer(max_age_seconds=300).is_fresh(NOW, now=NOW + 3_600)

    def test_a_future_timestamp_is_refused(self) -> None:
        # Without this, a signed response stamped far in the future stays
        # "fresh" indefinitely.
        assert not signer(max_age_seconds=300).is_fresh(NOW + 3_600, now=NOW)

    def test_the_boundary_is_inclusive(self) -> None:
        s = signer(max_age_seconds=300)
        assert s.is_fresh(NOW, now=NOW + 300)
        assert not s.is_fresh(NOW, now=NOW + 301)


class TestKeyId:
    def test_the_key_is_named_so_it_can_be_rotated(self) -> None:
        # Without a key id, changing the signing secret means every partner
        # breaks at the same instant.
        assert HmacResponseSigner(SECRET, "s2").key_id == "s2"
