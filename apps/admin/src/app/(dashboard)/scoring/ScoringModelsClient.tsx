'use client';

import { useActivateScoringModel, useScoringModels } from '@/features/scoring';
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from '@trustlens/ui';
import { toApiError } from '@trustlens/api-client';
import { useState } from 'react';
import { NewScoringModelForm } from './NewScoringModelForm';

export function ScoringModelsClient() {
  const { data: models, isPending, error } = useScoringModels();
  const activate = useActivateScoringModel();
  const [failure, setFailure] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  if (isPending)
    return (
      <div className="flex justify-center p-12">
        <Spinner label="Loading scoring models" />
      </div>
    );
  if (error)
    return (
      <main className="p-8">
        <Alert tone="error">Unable to load scoring models.</Alert>
      </main>
    );

  const activeModel = (models ?? []).find((m) => m.isActive);

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Scoring models</h1>
          <p className="mt-1 text-muted-foreground">
            Versioned weights determine the score. Activating a model preserves historical scores
            and queues a recomputation.
          </p>
        </div>
        {!creating && (
          <Button variant="outline" onClick={() => setCreating(true)}>
            New version
          </Button>
        )}
      </div>
      {failure && <Alert tone="error">{failure}</Alert>}

      {creating && <NewScoringModelForm active={activeModel} onDone={() => setCreating(false)} />}

      <div className="space-y-4">
        {(models ?? []).map((model) => (
          <Card key={model.id}>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle>
                  {model.name}{' '}
                  <span className="text-sm font-normal text-muted-foreground">{model.version}</span>
                </CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">{model.description}</p>
              </div>
              {model.isActive ? (
                <span className="rounded-md bg-risk-low-bg px-2 py-1 text-xs font-medium text-risk-low">
                  Active
                </span>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={activate.isPending}
                  onClick={() => {
                    setFailure(null);
                    activate.mutate(model.id, {
                      onError: (e) => setFailure(toApiError(e).message),
                    });
                  }}
                >
                  Activate
                </Button>
              )}
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex gap-6 text-sm">
                <span>
                  Total weight: <strong>{model.totalWeight.toFixed(0)}</strong>
                </span>
                <span>
                  Algorithm: <strong>{model.algorithm}</strong>
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {model.weights
                  .filter((weight) => weight.isEnabled)
                  .map((weight) => (
                    <div
                      key={weight.signalCode}
                      className="flex justify-between rounded-md border border-border/60 px-3 py-2 text-sm"
                    >
                      <span>{weight.signalCode}</span>
                      <span className="font-semibold tabular-nums">
                        {weight.weight}
                        {weight.hardCapOnFail != null ? ` · cap ${weight.hardCapOnFail}` : ''}
                      </span>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
