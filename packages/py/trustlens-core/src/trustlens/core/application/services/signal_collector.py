"""Signal collection: raw evidence -> scoreable `SignalEvaluation` objects.

This is the boundary where AI output and database facts stop being
implementation details and become evidence the scoring policy can price.
Adding a signal means adding a collector here plus a seed row and a weight -
`ScoringPolicy` is never modified (open/closed).

Every collector is defensive in one specific way: if the evidence it needs is
missing because a check has not run, it returns UNAVAILABLE, never FAIL. The
difference matters - UNAVAILABLE is excluded from the score denominator, while
FAIL costs the seller points they cannot recover without knowing why.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from trustlens.core.domain.entities import (
    EmailAddress,
    IdentityDocument,
    IdentityVerification,
    ListingAnalysis,
    PhoneNumber,
    SellerProfile,
    SignalEvaluation,
)
from trustlens.core.domain.entities.verification import IpReputation
from trustlens.core.domain.enums import (
    DocumentType,
    LineType,
    ReasonCode,
    SignalCategory,
    SignalCode,
    VerificationStatus,
)
from trustlens.core.domain.policies import AccountAgePolicy, DeviceLinkagePolicy

# Disposable-email domains that ship with the build. The full list is refreshed
# daily into Redis by a maintenance job; this bundled snapshot is the fallback
# so the check still works offline (NFR-8).
#: Disposable-email domains, checked offline (P8-05).
#:
#: A local list rather than an API on purpose. This feeds a scored signal,
#: so a third party being slow or down would either stall a verification or
#: cost a seller points for a reason they cannot appeal. A list that is a
#: little stale is a far better failure mode than a lookup that hangs.
#:
#: Started as ten domains, which caught almost nothing. These are the
#: services that actually appear in signups; `DISPOSABLE_EMAIL_LIST_URL` can
#: still layer a bigger downloaded list on top when one is configured.
FALLBACK_DISPOSABLE_DOMAINS = frozenset(
    {
        "10minutemail.com",
        "33mail.com",
        "anonaddy.com",
        "armyspy.com",
        "burnermail.io",
        "byom.de",
        "cool.fr.nf",
        "courriel.fr.nf",
        "cuvox.de",
        "dayrep.com",
        "dispostable.com",
        "einrot.com",
        "emailfake.com",
        "emailondeck.com",
        "fakeinbox.com",
        "fakemailgenerator.com",
        "fleckens.hu",
        "generator.email",
        "getnada.com",
        "grr.la",
        "guerrillamail.com",
        "guerrillamailblock.com",
        "gustr.com",
        "inboxbear.com",
        "inboxkitten.com",
        "jetable.fr.nf",
        "jetable.org",
        "jourrapide.com",
        "mail-temporaire.fr",
        "mailbox52.ga",
        "mailboxy.fun",
        "mailcatch.com",
        "maildrop.cc",
        "mailexpire.com",
        "mailhazard.com",
        "mailhz.me",
        "mailinater.com",
        "mailinator.com",
        "mailismagic.com",
        "mailnesia.com",
        "mailnull.com",
        "mailquack.com",
        "mailsac.com",
        "mailseal.de",
        "mailslurp.com",
        "mailtemp.info",
        "mailtemporaire.fr",
        "mailtothis.com",
        "mailtrash.net",
        "mailzilla.com",
        "mega.zik.dj",
        "mintemail.com",
        "moakt.com",
        "mohmal.com",
        "moncourrier.fr.nf",
        "monemail.fr.nf",
        "monmail.fr.nf",
        "mvrht.com",
        "mytemp.email",
        "mytrashmail.com",
        "nada.email",
        "nomail.xl.cx",
        "nospam.ze.tc",
        "nowhere.org",
        "nowmymail.com",
        "objectmail.com",
        "onewaymail.com",
        "owlpic.com",
        "pjjkp.com",
        "plexolan.de",
        "pokemail.net",
        "politikerclub.de",
        "proxymail.eu",
        "put2.net",
        "quickinbox.com",
        "rcpt.at",
        "recyclemail.dk",
        "rhyta.com",
        "rmqkr.net",
        "rtrtr.com",
        "s0ny.net",
        "safetymail.info",
        "saynotospams.com",
        "selfdestructingmail.com",
        "sendspamhere.com",
        "sharedmailbox.org",
        "sharklasers.com",
        "shieldedmail.com",
        "shortmail.net",
        "simplelogin.io",
        "sneakemail.com",
        "snkmail.com",
        "sofimail.com",
        "sogetthis.com",
        "spam4.me",
        "spamavert.com",
        "spambog.com",
        "spambox.us",
        "spamcannon.com",
        "spamcorptastic.com",
        "spamday.com",
        "spamfree24.org",
        "spamgourmet.com",
        "spamherelots.com",
        "spamhole.com",
        "spaml.com",
        "spamspot.com",
        "speed.1s.fr",
        "superrito.com",
        "superrito.net",
        "tafmail.com",
        "tagyourself.com",
        "teleworm.us",
        "temp-mail.io",
        "temp-mail.org",
        "tempail.com",
        "tempemail.com",
        "tempemail.net",
        "tempinbox.com",
        "tempmail.com",
        "tempmail.net",
        "tempmail2.com",
        "tempmailaddress.com",
        "tempmailer.com",
        "tempmailo.com",
        "tempomail.fr",
        "tempr.email",
        "tempthe.net",
        "thankyou2010.com",
        "thisisnotmyrealemail.com",
        "throwawaymail.com",
        "tmailinator.com",
        "trash-mail.com",
        "trashmail.com",
        "trashymail.com",
        "trbvm.com",
        "veryrealemail.com",
        "wegwerfemail.de",
        "wegwerfmail.de",
        "wetrainbayarea.com",
        "willselfdestruct.com",
        "wuzup.net",
        "wuzupmail.net",
        "xoxy.net",
        "yopmail.com",
        "yopmail.fr",
        "yopmail.net",
        "yourdomain.com",
        "zoemail.org",
    }
)

#: LLM/classifier labels that indicate an active scam pattern rather than a
#: merely low-quality listing.
CRITICAL_LISTING_LABELS = frozenset(
    {
        "advance_fee",
        "off_platform_contact",
        "urgency_pressure",
        "impersonation",
        "payment_outside_escrow",
        "stolen_goods",
    }
)


@dataclass(slots=True)
class SellerEvidence:
    """Everything the collectors need, gathered once.

    Assembled by the use case in a single pass over the repositories so that
    scoring is a pure function of this struct - which is what makes the whole
    engine testable without a database.
    """

    seller: SellerProfile
    now: datetime
    identity_documents: tuple[IdentityDocument, ...] = ()
    identity_verification: IdentityVerification | None = None
    duplicate_cnic_accounts: int = 0
    phone: PhoneNumber | None = None
    phone_reuse_accounts: int = 0
    email: EmailAddress | None = None
    linked_device_accounts: int = 0
    has_emulator_device: bool = False
    has_banned_shared_device: bool = False
    device_evidence_available: bool = False
    ip_reputation: IpReputation | None = None
    recent_access_days: int = 0
    listing_count: int = 0
    listing_analyses: tuple[ListingAnalysis, ...] = ()
    disposable_domains: frozenset[str] = FALLBACK_DISPOSABLE_DOMAINS


class SignalCollector:
    """Turns a `SellerEvidence` bundle into signal evaluations."""

    def __init__(
        self,
        *,
        age_policy: AccountAgePolicy | None = None,
        device_policy: DeviceLinkagePolicy | None = None,
        face_review_lower: float = 0.55,
    ) -> None:
        self._age = age_policy or AccountAgePolicy()
        self._devices = device_policy or DeviceLinkagePolicy()
        self._face_review_lower = face_review_lower

    def collect(self, evidence: SellerEvidence) -> list[SignalEvaluation]:
        return [
            self._identity_document(evidence),
            self._identity_face_match(evidence),
            self._phone_verified(evidence),
            self._phone_not_disposable(evidence),
            self._email_verified(evidence),
            self._email_not_disposable(evidence),
            self._device_not_shared(evidence),
            self._device_consistent(evidence),
            self._network_not_vpn(evidence),
            self._network_geo_consistent(evidence),
            self._account_age(evidence),
            self._activity_consistent(evidence),
            self._listing_content_safe(evidence),
            self._listing_price_realistic(evidence),
        ]

    # ── IDENTITY ─────────────────────────────────────────────────────

    def _identity_document(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.IDENTITY_DOCUMENT_VALID, SignalCategory.IDENTITY
        front = next(
            (d for d in e.identity_documents if d.document_type == DocumentType.CNIC_FRONT), None
        )

        if front is None:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.IDENTITY_NOT_SUBMITTED,
                "No government ID has been submitted.",
            )
        if front.status in {VerificationStatus.PENDING, VerificationStatus.PROCESSING}:
            return SignalEvaluation.unavailable(
                code,
                cat,
                "The submitted ID is still being checked.",
                source_table="identity_documents",
                source_id=front.id,
            )
        if front.status == VerificationStatus.FAILED:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.CNIC_UNREADABLE,
                "The submitted ID could not be read clearly.",
                confidence=0.9,
                source_table="identity_documents",
                source_id=front.id,
            )
        if front.is_expired_on(e.now.date()):
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.CNIC_EXPIRED,
                "The submitted ID has expired.",
                evidence={"expiry_date": str(front.fields.expiry_date)},
                source_table="identity_documents",
                source_id=front.id,
            )
        # One national ID across several accounts is the classic multi-account
        # fraud pattern, and it must not be silently outweighed by other passes.
        if e.duplicate_cnic_accounts >= 2:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.CNIC_DUPLICATE,
                "This ID document is registered to more than one seller account.",
                evidence={"linked_accounts": e.duplicate_cnic_accounts},
                source_table="identity_documents",
                source_id=front.id,
            )
        if front.status != VerificationStatus.VERIFIED:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.IDENTITY_PENDING_REVIEW,
                "The submitted ID has not been approved.",
                source_table="identity_documents",
                source_id=front.id,
            )

        confidence = front.ocr_confidence if front.ocr_confidence is not None else 0.9
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.IDENTITY_VERIFIED,
            "A valid government ID was submitted and checked.",
            confidence=min(1.0, max(0.0, confidence)),
            evidence={"ocr_confidence": round(confidence, 3)},
            source_table="identity_documents",
            source_id=front.id,
        )

    def _identity_face_match(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.IDENTITY_FACE_MATCH, SignalCategory.IDENTITY
        v = e.identity_verification

        if v is None:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.IDENTITY_NOT_SUBMITTED,
                "No selfie has been submitted for comparison with the ID photo.",
            )
        if v.decision in {VerificationStatus.PENDING, VerificationStatus.PROCESSING}:
            return SignalEvaluation.unavailable(
                code,
                cat,
                "The selfie comparison is still running.",
                source_table="identity_verifications",
                source_id=v.id,
            )
        if v.face_similarity is None:
            return SignalEvaluation.unavailable(
                code,
                cat,
                "The selfie comparison could not be completed.",
                source_table="identity_verifications",
                source_id=v.id,
            )

        similarity = v.face_similarity
        threshold = v.threshold_used if v.threshold_used is not None else 0.70
        ev = {"similarity": round(similarity, 4), "threshold": threshold}

        if v.is_verified or similarity >= threshold:
            return SignalEvaluation.passed(
                code,
                cat,
                ReasonCode.FACE_MATCH_HIGH,
                "The selfie matches the photo on the submitted ID.",
                confidence=min(1.0, similarity),
                evidence=ev,
                source_table="identity_verifications",
                source_id=v.id,
            )
        # Borderline results go to a human rather than becoming an automatic
        # failure: face matching has known demographic error-rate disparities,
        # and a false positive here costs a real person their livelihood.
        if similarity >= self._face_review_lower:
            return SignalEvaluation.partial(
                code,
                cat,
                0.5,
                ReasonCode.FACE_MATCH_BORDERLINE,
                "The selfie partly matches the ID photo and is awaiting manual review.",
                confidence=0.5,
                evidence=ev,
                source_table="identity_verifications",
                source_id=v.id,
            )
        return SignalEvaluation.failed(
            code,
            cat,
            ReasonCode.FACE_MATCH_LOW,
            "The selfie does not match the photo on the submitted ID.",
            confidence=min(1.0, 1.0 - similarity),
            evidence=ev,
            source_table="identity_verifications",
            source_id=v.id,
        )

    # ── PHONE ────────────────────────────────────────────────────────

    def _phone_verified(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.PHONE_VERIFIED, SignalCategory.PHONE
        if e.phone is None:
            return SignalEvaluation.failed(
                code, cat, ReasonCode.PHONE_NOT_VERIFIED, "No phone number has been added."
            )
        if not e.phone.is_verified:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.PHONE_NOT_VERIFIED,
                "The phone number has not been confirmed with a code.",
                source_table="phone_numbers",
                source_id=e.phone.id,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.PHONE_VERIFIED_OK,
            "The phone number was confirmed with a one-time code.",
            source_table="phone_numbers",
            source_id=e.phone.id,
        )

    def _phone_not_disposable(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.PHONE_NOT_DISPOSABLE, SignalCategory.PHONE
        if e.phone is None:
            return SignalEvaluation.not_applicable(
                code, cat, ReasonCode.PHONE_NOT_VERIFIED, "No phone number has been added."
            )
        if e.phone.line_type == LineType.UNKNOWN and not e.phone.is_disposable:
            # We could not determine the line type; scoring it as a failure
            # would penalise the seller for a lookup we did not perform.
            return SignalEvaluation.unavailable(
                code,
                cat,
                "The phone number type could not be checked.",
                source_table="phone_numbers",
                source_id=e.phone.id,
            )
        if e.phone.line_type == LineType.VOIP or e.phone.is_disposable:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.PHONE_LINE_TYPE_VOIP,
                "The phone number is an internet (VOIP) number rather than a mobile SIM.",
                confidence=0.9,
                evidence={"line_type": e.phone.line_type.value},
                source_table="phone_numbers",
                source_id=e.phone.id,
            )
        if e.phone_reuse_accounts >= 3:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.PHONE_REUSED,
                "This phone number is linked to several other accounts.",
                evidence={"linked_accounts": e.phone_reuse_accounts},
                source_table="phone_numbers",
                source_id=e.phone.id,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.PHONE_VERIFIED_OK,
            "The phone number is a normal mobile number.",
            evidence={"line_type": e.phone.line_type.value},
            source_table="phone_numbers",
            source_id=e.phone.id,
        )

    # ── EMAIL ────────────────────────────────────────────────────────

    def _email_verified(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.EMAIL_VERIFIED, SignalCategory.EMAIL
        if e.email is None or not e.email.is_verified:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.EMAIL_NOT_VERIFIED,
                "The email address has not been confirmed.",
                source_table="email_addresses",
                source_id=e.email.id if e.email else None,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.EMAIL_VERIFIED_OK,
            "The email address was confirmed.",
            source_table="email_addresses",
            source_id=e.email.id,
        )

    def _email_not_disposable(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.EMAIL_NOT_DISPOSABLE, SignalCategory.EMAIL
        if e.email is None:
            return SignalEvaluation.not_applicable(
                code, cat, ReasonCode.EMAIL_NOT_VERIFIED, "No email address on file."
            )

        domain = e.email.domain.lower()
        if e.email.is_disposable or domain in e.disposable_domains:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.EMAIL_DOMAIN_DISPOSABLE,
                "The email address uses a temporary email service.",
                evidence={"domain": domain},
                source_table="email_addresses",
                source_id=e.email.id,
            )
        if e.email.mx_valid is False:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.EMAIL_DOMAIN_NEW,
                "The email domain cannot receive mail.",
                evidence={"domain": domain},
                source_table="email_addresses",
                source_id=e.email.id,
            )
        if e.email.domain_age_days is not None and e.email.domain_age_days < 180:
            return SignalEvaluation.partial(
                code,
                cat,
                0.5,
                ReasonCode.EMAIL_DOMAIN_NEW,
                "The email domain was registered very recently.",
                confidence=0.8,
                evidence={"domain_age_days": e.email.domain_age_days},
                source_table="email_addresses",
                source_id=e.email.id,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.EMAIL_VERIFIED_OK,
            "The email address uses a normal, established domain.",
            evidence={"domain": domain},
            source_table="email_addresses",
            source_id=e.email.id,
        )

    # ── DEVICE ───────────────────────────────────────────────────────

    def _device_not_shared(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.DEVICE_NOT_SHARED, SignalCategory.DEVICE
        if not e.device_evidence_available:
            return SignalEvaluation.unavailable(
                code, cat, "No device information has been recorded yet."
            )

        if e.has_banned_shared_device:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.DEVICE_SHARED_MANY_ACCOUNTS,
                "This device was used by an account that was banned for fraud.",
                evidence={"banned_account_on_device": True},
            )

        ratio = self._devices.ratio_for(e.linked_device_accounts)
        ev = {"linked_accounts": e.linked_device_accounts}
        if ratio >= 1.0:
            return SignalEvaluation.passed(
                code,
                cat,
                ReasonCode.DEVICE_CLEAN,
                "This seller's devices are not shared with other accounts.",
                evidence=ev,
            )
        if ratio <= 0.0:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.DEVICE_SHARED_MANY_ACCOUNTS,
                "This device is linked to several other seller accounts.",
                confidence=0.85,
                evidence=ev,
            )
        return SignalEvaluation.partial(
            code,
            cat,
            ratio,
            ReasonCode.DEVICE_SHARED_MANY_ACCOUNTS,
            "This device is shared with a few other accounts.",
            confidence=0.8,
            evidence=ev,
        )

    def _device_consistent(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.DEVICE_CONSISTENT, SignalCategory.DEVICE
        if not e.device_evidence_available:
            return SignalEvaluation.unavailable(
                code, cat, "No device information has been recorded yet."
            )
        if e.has_emulator_device:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.DEVICE_EMULATOR,
                "The account is used from an emulated or automated environment.",
                confidence=0.75,
            )
        return SignalEvaluation.passed(
            code, cat, ReasonCode.DEVICE_CLEAN, "The account is used from ordinary devices."
        )

    # ── NETWORK ──────────────────────────────────────────────────────

    def _network_not_vpn(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.NETWORK_NOT_VPN, SignalCategory.NETWORK
        rep = e.ip_reputation
        if rep is None:
            return SignalEvaluation.unavailable(code, cat, "Network information is not available.")

        ev = {
            "is_vpn": rep.is_vpn,
            "is_proxy": rep.is_proxy,
            "is_datacenter": rep.is_datacenter,
            "provider": rep.provider,
        }
        # Offline fallback data is coarser than a live provider, so the same
        # verdict is published with lower confidence rather than pretended equal.
        confidence = 0.6 if rep.provider == "offline" else 0.9

        if rep.is_tor or rep.is_proxy:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.NETWORK_VPN_DETECTED,
                "The seller connects through an anonymising proxy, hiding their location.",
                confidence=confidence,
                evidence=ev,
            )
        if rep.is_vpn:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.NETWORK_VPN_DETECTED,
                "The seller connects through a VPN, hiding their location.",
                confidence=confidence,
                evidence=ev,
            )
        if rep.is_datacenter:
            return SignalEvaluation.partial(
                code,
                cat,
                0.4,
                ReasonCode.NETWORK_DATACENTER_IP,
                "The seller connects from a data centre rather than a home or mobile network.",
                confidence=confidence,
                evidence=ev,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.NETWORK_CLEAN,
            "The seller connects from an ordinary consumer network.",
            confidence=confidence,
            evidence=ev,
        )

    def _network_geo_consistent(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.NETWORK_GEO_CONSISTENT, SignalCategory.NETWORK
        rep = e.ip_reputation
        declared = (e.seller.country_code or "").upper()

        if rep is None or not rep.country_code or not declared:
            return SignalEvaluation.unavailable(code, cat, "Location could not be compared.")
        if rep.is_anonymised:
            # A VPN exit node's country says nothing about the seller, so this
            # signal abstains rather than punishing twice for the same fact.
            return SignalEvaluation.unavailable(
                code, cat, "Location cannot be compared while connecting through a VPN or proxy."
            )

        observed = rep.country_code.upper()
        ev = {"declared_country": declared, "observed_country": observed}
        if observed == declared:
            return SignalEvaluation.passed(
                code,
                cat,
                ReasonCode.NETWORK_CLEAN,
                "The seller's connection location matches their stated location.",
                confidence=0.85,
                evidence=ev,
            )
        return SignalEvaluation.failed(
            code,
            cat,
            ReasonCode.GEO_MISMATCH,
            "The seller's connection location does not match their stated location.",
            confidence=0.8,
            evidence=ev,
        )

    # ── BEHAVIOUR ────────────────────────────────────────────────────

    def _account_age(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.ACCOUNT_AGE, SignalCategory.BEHAVIOUR
        days = e.seller.account_age_days(e.now)
        ratio = self._age.ratio_for(days)
        ev = {"account_age_days": days}

        if ratio >= 1.0:
            return SignalEvaluation.passed(
                code,
                cat,
                ReasonCode.ACCOUNT_ESTABLISHED,
                "The account has been active for a long time.",
                evidence=ev,
            )
        if ratio <= 0.0:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.ACCOUNT_TOO_NEW,
                "The account was created very recently.",
                evidence=ev,
            )
        return SignalEvaluation.partial(
            code,
            cat,
            ratio,
            ReasonCode.ACCOUNT_TOO_NEW,
            "The account is fairly new.",
            evidence=ev,
        )

    def _activity_consistent(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.ACTIVITY_CONSISTENT, SignalCategory.BEHAVIOUR
        if e.recent_access_days <= 0:
            return SignalEvaluation.unavailable(code, cat, "No recent activity has been recorded.")

        ev = {"active_days_last_30": e.recent_access_days}
        if e.recent_access_days >= 5:
            return SignalEvaluation.passed(
                code,
                cat,
                ReasonCode.ACTIVITY_NORMAL,
                "The seller uses the account regularly.",
                confidence=0.8,
                evidence=ev,
            )
        return SignalEvaluation.partial(
            code,
            cat,
            0.5,
            ReasonCode.ACTIVITY_IRREGULAR,
            "The seller has used the account only occasionally.",
            confidence=0.7,
            evidence=ev,
        )

    # ── LISTING ──────────────────────────────────────────────────────

    def _listing_content_safe(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.LISTING_CONTENT_SAFE, SignalCategory.LISTING
        if e.listing_count == 0:
            return SignalEvaluation.not_applicable(
                code, cat, ReasonCode.NO_LISTINGS, "This seller has no listings yet."
            )
        if not e.listing_analyses:
            return SignalEvaluation.unavailable(code, cat, "Listings have not been analysed yet.")

        mean_risk = sum(a.risk_score for a in e.listing_analyses) / len(e.listing_analyses)
        all_labels = {label for a in e.listing_analyses for label in a.label_codes}
        critical = all_labels & CRITICAL_LISTING_LABELS
        mean_conf = sum(a.confidence for a in e.listing_analyses) / len(e.listing_analyses)
        ev = {
            "mean_risk_score": round(mean_risk, 2),
            "listings_analysed": len(e.listing_analyses),
            "labels": sorted(all_labels),
        }

        if critical:
            reason = (
                ReasonCode.LISTING_OFF_PLATFORM_CONTACT
                if "off_platform_contact" in critical
                else ReasonCode.LISTING_URGENCY_PRESSURE
                if "urgency_pressure" in critical
                else ReasonCode.LISTING_SCAM_PATTERN
            )
            return SignalEvaluation.failed(
                code,
                cat,
                reason,
                "Listings show patterns commonly used in scams.",
                confidence=min(1.0, mean_conf),
                evidence=ev,
            )
        if mean_risk >= 60:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.LISTING_SCAM_PATTERN,
                "Listings were assessed as high risk.",
                confidence=min(1.0, mean_conf),
                evidence=ev,
            )
        if mean_risk >= 30:
            ratio = round(1.0 - (mean_risk - 30) / 30, 3)
            return SignalEvaluation.partial(
                code,
                cat,
                ratio,
                ReasonCode.LISTING_SCAM_PATTERN,
                "Some listings contain wording that is often used in scams.",
                confidence=min(1.0, mean_conf),
                evidence=ev,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.LISTINGS_CLEAN,
            "Listings look normal, with no scam patterns detected.",
            confidence=min(1.0, mean_conf),
            evidence=ev,
        )

    def _listing_price_realistic(self, e: SellerEvidence) -> SignalEvaluation:
        code, cat = SignalCode.LISTING_PRICE_REALISTIC, SignalCategory.LISTING
        if e.listing_count == 0:
            return SignalEvaluation.not_applicable(
                code, cat, ReasonCode.NO_LISTINGS, "This seller has no listings yet."
            )

        deviations = [
            a.price_deviation_pct for a in e.listing_analyses if a.price_deviation_pct is not None
        ]
        if not deviations:
            return SignalEvaluation.unavailable(code, cat, "Listing prices could not be compared.")

        # Only underpricing is suspicious: "too good to be true" is the pattern
        # in the proposal. An overpriced listing is a bad deal, not a scam.
        worst = min(deviations)
        ev = {"worst_price_deviation_pct": round(worst, 2)}

        if worst <= -60:
            return SignalEvaluation.failed(
                code,
                cat,
                ReasonCode.PRICE_TOO_GOOD_TO_BE_TRUE,
                "Prices are far below the normal range for similar items.",
                confidence=0.85,
                evidence=ev,
            )
        if worst <= -35:
            return SignalEvaluation.partial(
                code,
                cat,
                0.5,
                ReasonCode.PRICE_TOO_GOOD_TO_BE_TRUE,
                "Some prices are noticeably below the normal range.",
                confidence=0.75,
                evidence=ev,
            )
        return SignalEvaluation.passed(
            code,
            cat,
            ReasonCode.PRICE_REALISTIC,
            "Prices are in line with similar items.",
            confidence=0.8,
            evidence=ev,
        )


__all__ = [
    "CRITICAL_LISTING_LABELS",
    "FALLBACK_DISPOSABLE_DOMAINS",
    "SellerEvidence",
    "SignalCollector",
]
