import { PartnerList } from '@/features/partners';
import { Card, CardContent, CardHeader, CardTitle } from '@trustlens/ui';

export const metadata = { title: 'API clients' };

export default function ApiClientsPage() {
  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">API clients</h1>
      <p className="mt-1 text-muted-foreground">
        Marketplaces consuming the public Trust Score API, and the keys they hold.
      </p>

      <div className="mt-8">
        <PartnerList />
      </div>

      <Card className="mt-8">
        <CardHeader>
          <CardTitle>How keys work</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong>Shown once.</strong> Only an argon2 hash is stored, so a key cannot be looked up
            after it is issued. A partner who loses theirs needs a rotation, not a lookup — which is
            also why a database dump is not a set of live credentials.
          </p>
          <p>
            <strong>Rotate for hygiene, revoke for leaks.</strong> Rotating issues a replacement and
            expires the old key after a 24-hour overlap, so the partner can redeploy without an
            outage. Revoking is immediate and has no overlap.
          </p>
          <p>
            <strong>Suspending stops everything at once.</strong> Use it when you need a partner off
            the API now, rather than hunting down each key they hold.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
