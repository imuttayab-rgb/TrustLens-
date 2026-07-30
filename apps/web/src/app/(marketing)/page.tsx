import { CATEGORY_LABELS, CATEGORY_MAX_POINTS, SIGNAL_CATEGORIES } from '@trustlens/constants';
import { Button, Card, CardContent, CardHeader, CardTitle, ScoreGauge } from '@trustlens/ui';
import Link from 'next/link';

export default function LandingPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <section className="grid items-center gap-12 md:grid-cols-2">
        <div>
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            Know who you are buying from.
          </h1>
          <p className="text-muted-foreground mt-4 text-lg">
            TrustLens verifies a seller&apos;s identity, phone, email, device and listings, then
            gives you one score out of 100 — and tells you exactly why.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg">
              <Link href="/check">Check a seller</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/register">Get verified as a seller</Link>
            </Button>
          </div>
        </div>

        <div className="flex justify-center">
          <ScoreGauge score={82} riskLevel="LOW" size="lg" caption="Example score" />
        </div>
      </section>

      <section className="mt-20">
        <h2 className="text-2xl font-semibold">Seven independent checks</h2>
        <p className="text-muted-foreground mt-2">
          A scammer would have to defeat every one of these separately. The points show how much each
          contributes to the score.
        </p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {SIGNAL_CATEGORIES.map((category) => (
            <Card key={category}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{CATEGORY_LABELS[category]}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold tabular-nums">
                  {CATEGORY_MAX_POINTS[category]}
                  <span className="text-muted-foreground text-sm font-normal"> points</span>
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="bg-muted/40 mt-20 rounded-xl p-8">
        <h2 className="text-2xl font-semibold">Why the score is explainable</h2>
        <p className="text-muted-foreground mt-2 max-w-2xl">
          AI reads the ID, compares the selfie and analyses the listings — but it never decides the
          score. A fixed, published set of rules turns that evidence into points, so the same
          information always produces the same result, and every seller can see exactly which check
          cost them what.
        </p>
      </section>
    </main>
  );
}
