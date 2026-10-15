/** Next.js route/layout composition for (marketing)/privacy: page. */
import Link from 'next/link';

export const metadata = {
  title: 'Privacy Policy · TrustLens',
  description: 'What TrustLens collects, why, and for how long - including CNIC and selfie data.',
};

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24 border-t border-border/60 pt-8">
      <h2 className="text-lg font-bold tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-14 sm:px-8">
      <header>
        <p className="text-sm font-medium text-brand">Version 1.0</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Privacy Policy</h1>
        <p className="mt-3 text-muted-foreground">
          TrustLens holds sensitive data - CNIC images and a selfie - because that is what verifying
          an identity requires. This page explains what we collect, why, and for how long, in plain
          terms rather than boilerplate.
        </p>
      </header>

      <div className="mt-8 space-y-8">
        <Section id="what-we-collect" title="1. What we collect">
          <ul className="list-inside list-disc space-y-1">
            <li>Account details: name, email address, password (hashed, never stored in full).</li>
            <li>
              Identity verification: photos of the front and back of your CNIC, and a selfie, only
              if you choose to verify your identity.
            </li>
            <li>Phone number, for OTP verification.</li>
            <li>Listings you create: title, description, price, category, city, photos.</li>
            <li>
              Device and network signals used for fraud detection (device fingerprint, IP-derived
              signals) - never used to identify you personally outside of that purpose.
            </li>
          </ul>
        </Section>

        <Section id="why" title="2. Why we collect it">
          <p>
            Every field above feeds a specific check that contributes to your Trust Score: a
            verified identity, a verified phone, a verified email, and listings that pass a
            scam-pattern check. We do not collect anything beyond what a check actually needs.
          </p>
        </Section>

        <Section id="biometric" title="3. Biometric processing and consent">
          <p>
            Comparing your selfie against your CNIC photo is biometric processing. We only run it
            after you give explicit consent on the identity verification screen, and you can
            withdraw that consent at any time from your account settings.
          </p>
          <p>
            The extracted details (name, CNIC number, date of birth as read from the document) are
            stored encrypted.{' '}
            <strong>
              The CNIC and selfie images themselves are deleted 90 days after a final decision
            </strong>{' '}
            on your verification - approved or rejected. The decision and the score it produced are
            kept, because a Trust Score has to remain explainable and appealable even after the
            source images are gone.
          </p>
        </Section>

        <Section id="sharing" title="4. Who sees your data">
          <p>
            Your CNIC and selfie are visible only to you and to TrustLens staff reviewing a flagged
            verification, through short-lived signed links that expire quickly. They are never shown
            to buyers, other sellers, or partner marketplaces.
          </p>
          <p>
            Your public Trust Score page shows your score, risk band, and which categories of check
            you passed - never your CNIC number, phone number, email address, or any image. The
            partner API integration marketplaces use to read scores returns the same PII-free
            projection.
          </p>
        </Section>

        <Section id="your-rights" title="5. Your rights">
          <p>
            You can request a copy of the personal data TrustLens holds about you, and you can
            request that it be deleted, from your account settings. Deleting your account removes
            your listings and verification images; the score history behind an already-issued Trust
            Score may be retained in de-identified form where needed to explain a decision under
            appeal.
          </p>
        </Section>

        <Section id="retention" title="6. How long we keep things">
          <ul className="list-inside list-disc space-y-1">
            <li>CNIC and selfie images: deleted 90 days after a final verification decision.</li>
            <li>
              Account and listing data: kept while your account is active, deleted on request or
              account closure, subject to the appeal-evidence exception above.
            </li>
            <li>
              Security logs (login attempts, device signals): kept for a limited window to detect
              abuse, then purged.
            </li>
          </ul>
        </Section>

        <Section id="contact" title="7. Contact">
          <p>
            Questions about this policy, or a data access/deletion request, can be sent through the{' '}
            <Link href="/help" className="text-primary underline-offset-4 hover:underline">
              Help page
            </Link>
            .
          </p>
        </Section>
      </div>
    </main>
  );
}
