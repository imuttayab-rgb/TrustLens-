import { CATEGORY_LABELS, CATEGORY_MAX_POINTS, SIGNAL_CATEGORIES } from '@trustlens/constants';
import { Card, CardContent, CardHeader, CardTitle } from '@trustlens/ui';

export const metadata = { title: 'Scoring models' };

export default function ScoringPage() {
  const total = SIGNAL_CATEGORIES.reduce((sum, c) => sum + CATEGORY_MAX_POINTS[c], 0);

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Scoring models</h1>
      <p className="text-muted-foreground mt-1">
        Weights are data, not code — tune them here, simulate, then activate.
      </p>

      <Card className="mt-8 max-w-2xl">
        <CardHeader>
          <CardTitle>Active model weighting</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="divide-border divide-y">
            {SIGNAL_CATEGORIES.map((category) => (
              <li key={category} className="flex items-center justify-between py-2">
                <span>{CATEGORY_LABELS[category]}</span>
                <span className="font-semibold tabular-nums">
                  {CATEGORY_MAX_POINTS[category]}
                </span>
              </li>
            ))}
            <li className="flex items-center justify-between py-2 font-semibold">
              <span>Total</span>
              <span className="tabular-nums">{total}</span>
            </li>
          </ul>
          <p className="text-muted-foreground mt-4 text-sm">
            Enabled weights must sum to exactly 100. The form, the domain and a database CHECK
            constraint all enforce it, so an invalid model cannot be activated.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
