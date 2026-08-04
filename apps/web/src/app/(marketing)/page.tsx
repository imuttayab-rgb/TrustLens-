import { ChecksGrid, Hero, Reveal } from '@/features/marketing';
import { Button } from '@trustlens/ui';
import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Know your seller before you pay',
  description:
    'TrustLens checks a seller’s ID, phone, email, device and listings, then gives you one score ' +
    'out of 100 — and tells you exactly which check earned or cost each point.',
};

/**
 * Three steps, because the process genuinely is sequential: evidence has to
 * exist before it can be weighed, and it has to be weighed before anyone can
 * be shown a reason. Numbering something that is not a sequence would be
 * decoration; here the order is the point.
 */
const STEPS = [
  {
    n: '01',
    title: 'Evidence is collected',
    body: 'The seller submits an ID and a selfie, confirms a phone and an email, and posts listings. Each arrives as a separate, independent signal.',
  },
  {
    n: '02',
    title: 'Rules turn it into points',
    body: 'A fixed, published rule set converts that evidence into points. AI reads documents and listings, but never decides the score — so the same evidence always produces the same number.',
  },
  {
    n: '03',
    title: 'You see the reasons',
    body: 'The score arrives with every check listed, what each was worth, and what it scored. A failed critical check caps the total no matter what else passed.',
  },
] as const;

const LIMITS = [
  {
    term: 'What TrustLens cannot do',
    detail:
      'It cannot confirm a CNIC against NADRA — no public service exists for that. It checks that the card is internally consistent and that the face on it matches the seller.',
  },
  {
    term: 'What a low score means',
    detail:
      'That the checks did not pass — not that the person is a criminal. The reasons are always shown, so it can be fixed or disputed.',
  },
  {
    term: 'What happens to documents',
    detail:
      'They are used for the check, stored encrypted, and deleted once a decision is final and the appeal window has closed.',
  },
] as const;

export default function LandingPage() {
  return (
    <main>
      <Hero />

      <section id="checks" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-20 sm:px-8">
        <Reveal>
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Six checks a scammer has to beat separately
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground">
            Any one of these can be faked with enough effort. Faking all six, consistently, on one
            account, is a different problem — and the points show exactly how much each is worth.
          </p>
        </Reveal>

        <div className="mt-10">
          <ChecksGrid />
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-20 border-y border-border/70">
        <div className="mx-auto max-w-6xl px-5 py-20 sm:px-8">
          <Reveal>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">How a score is made</h2>
          </Reveal>

          <ol className="mt-10 grid gap-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <Reveal as="li" key={step.n} delayMs={index * 90}>
                <div className="border-l-2 border-brand/30 pl-5">
                  <span className="text-xs font-bold tracking-[0.2em] text-brand">{step.n}</span>
                  <h3 className="mt-2 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      <section id="explainable" className="mx-auto max-w-6xl scroll-mt-20 px-5 py-20 sm:px-8">
        <div className="grid items-start gap-10 lg:grid-cols-2">
          <Reveal>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              A number you can argue with
            </h2>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground">
              Most trust signals are a badge you either have or you don&apos;t. That tells a buyer
              nothing once everyone has one, and it gives a seller no way to disagree.
            </p>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground">
              Every TrustLens score arrives with its full working: which checks ran, what each was
              worth, and what it scored. A check that could not run is excluded rather than counted
              as a failure — nobody is penalised for our outage. And any seller who believes a check
              is wrong can appeal it.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Button
                asChild
                size="lg"
                className="bg-gradient-to-r from-brand to-brand-2 font-semibold text-[hsl(var(--background))] transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
              >
                <Link href="/check">Check a seller</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/register">Get verified</Link>
              </Button>
            </div>
          </Reveal>

          <Reveal delayMs={120}>
            <dl className="divide-y divide-border/70 rounded-xl border border-border/70 bg-card/50">
              {LIMITS.map((row) => (
                <div key={row.term} className="p-5">
                  <dt className="text-sm font-semibold">{row.term}</dt>
                  <dd className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {row.detail}
                  </dd>
                </div>
              ))}
            </dl>
          </Reveal>
        </div>
      </section>
    </main>
  );
}
