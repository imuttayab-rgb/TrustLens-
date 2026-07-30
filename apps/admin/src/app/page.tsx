import { adminFetch } from '@/lib/server-api';
import { Card, CardContent, CardHeader, CardTitle } from '@trustlens/ui';

export const dynamic = 'force-dynamic';

export default async function AdminOverview() {
  const status = await adminFetch<{ scoringModelVersion: string }>('/public/v1/status');

  return (
    <main className="p-8">
      <h1 className="text-2xl font-bold">Overview</h1>
      <p className="text-muted-foreground mt-1">
        Operational state of the scoring pipeline.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active scoring model</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{status?.scoringModelVersion ?? 'unknown'}</p>
          </CardContent>
        </Card>
      </div>

      <section className="bg-muted/40 mt-10 rounded-xl p-6">
        <h2 className="font-semibold">Before changing scoring weights</h2>
        <p className="text-muted-foreground mt-2 max-w-2xl text-sm">
          Always run a simulation first. Activating a model re-scores every seller, and the
          distribution delta tells you how many change risk band before it affects anyone. Old
          scores are never rewritten - each one keeps a reference to the model that produced it.
        </p>
      </section>
    </main>
  );
}
