/** Next.js route/layout composition for (dashboard)/appeals: page. */
import { AppealQueue } from '@/features/appeals';
import { Card, CardContent, CardHeader, CardTitle } from '@trustlens/ui';

export const metadata = { title: 'Appeals' };

export default function AppealsPage() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Appeals</h1>
      <p className="mt-1 text-muted-foreground">
        Each appeal references one specific score computation, with its breakdown frozen at the
        moment it was calculated.
      </p>

      <div className="mt-8">
        <AppealQueue />
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>Resolving an appeal</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Three outcomes are possible:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong>Recompute</strong> — the underlying evidence was corrected.
            </li>
            <li>
              <strong>Override</strong> — admin only, with a written reason, and it expires after 90
              days.
            </li>
            <li>
              <strong>Reject</strong> — with an explanation the seller can read.
            </li>
          </ul>
          <p>Every outcome notifies the seller and is written to the audit log.</p>
        </CardContent>
      </Card>
    </main>
  );
}
