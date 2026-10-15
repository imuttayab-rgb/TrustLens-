/** Next.js route/layout composition for (dashboard)/scoring: NewScoringModelForm. */
'use client';

import { useCreateScoringModel, type ScoringModel } from '@/features/scoring';
import { toApiError } from '@trustlens/api-client';
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Field,
  Input,
} from '@trustlens/ui';
import { useState } from 'react';

interface DraftWeight {
  signalCode: string;
  weight: string;
  hardCapOnFail: string;
  isEnabled: boolean;
}

function cloneWeights(source: ScoringModel | undefined): DraftWeight[] {
  return (source?.weights ?? []).map((w) => ({
    signalCode: w.signalCode,
    weight: String(w.weight),
    hardCapOnFail: w.hardCapOnFail != null ? String(w.hardCapOnFail) : '',
    isEnabled: w.isEnabled,
  }));
}

function totalOf(weights: DraftWeight[]): number {
  return weights
    .filter((w) => w.isEnabled)
    .reduce((sum, w) => sum + (Number.parseFloat(w.weight) || 0), 0);
}

/**
 * Publishing a new scoring-model version. Starts from a clone of the
 * currently active model's weights - editing 14 signal weights from a blank
 * form is how someone fat-fingers the sum away from 100. The version this
 * creates is always a draft (POST /admin/scoring-models never activates);
 * making it live is still the separate, audited "Activate" action below.
 */
export function NewScoringModelForm({
  active,
  onDone,
}: {
  active: ScoringModel | undefined;
  onDone: () => void;
}) {
  const create = useCreateScoringModel();
  const [version, setVersion] = useState('');
  const [name, setName] = useState(active ? `${active.name} (revised)` : '');
  const [description, setDescription] = useState(active?.description ?? '');
  const [weights, setWeights] = useState<DraftWeight[]>(() => cloneWeights(active));
  const [failure, setFailure] = useState<string | null>(null);

  const total = totalOf(weights);
  const totalOk = Math.abs(total - 100) < 0.001;

  function updateWeight(index: number, patch: Partial<DraftWeight>) {
    setWeights((prev) => prev.map((w, i) => (i === index ? { ...w, ...patch } : w)));
  }

  function submit() {
    setFailure(null);
    create.mutate(
      {
        version: version.trim(),
        name: name.trim(),
        description: description.trim(),
        algorithm: active?.algorithm ?? 'WEIGHTED_SUM',
        weights: weights.map((w) => ({
          signalCode: w.signalCode,
          weight: Number.parseFloat(w.weight) || 0,
          hardCapOnFail:
            w.hardCapOnFail.trim() === '' ? null : Number.parseInt(w.hardCapOnFail, 10),
          isEnabled: w.isEnabled,
        })),
      },
      {
        onError: (e) => setFailure(toApiError(e).message),
        onSuccess: onDone,
      },
    );
  }

  const canSubmit =
    version.trim().length > 0 && name.trim().length > 0 && totalOk && weights.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>New scoring model version</CardTitle>
        <p className="mt-1 text-sm text-muted-foreground">
          {active
            ? `Starting from a copy of the active model (${active.version}). Publishing here only creates the draft — activate it separately once you're ready.`
            : 'No active model to copy from yet — add at least one signal weight below.'}
        </p>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field htmlFor="new-model-version" label="Version" required>
            <Input
              id="new-model-version"
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              placeholder="v3"
            />
          </Field>
          <Field htmlFor="new-model-name" label="Name" required>
            <Input id="new-model-name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
        </div>
        <Field htmlFor="new-model-description" label="Description">
          <Input
            id="new-model-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>

        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-sm font-medium">Signal weights</h3>
            <span
              className={totalOk ? 'text-sm text-risk-low' : 'text-sm font-semibold text-risk-high'}
            >
              Total: {total.toFixed(1)} / 100{totalOk ? '' : ' — must equal 100'}
            </span>
          </div>
          <div className="space-y-2">
            {weights.map((w, i) => (
              <div
                key={w.signalCode}
                className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-3 rounded-md border border-border/60 px-3 py-2 text-sm"
              >
                <span className={w.isEnabled ? '' : 'text-muted-foreground line-through'}>
                  {w.signalCode}
                </span>
                <Input
                  aria-label={`${w.signalCode} weight`}
                  className="w-20"
                  inputMode="decimal"
                  value={w.weight}
                  onChange={(e) => updateWeight(i, { weight: e.target.value })}
                />
                <Input
                  aria-label={`${w.signalCode} hard cap on fail`}
                  className="w-20"
                  inputMode="numeric"
                  placeholder="cap"
                  value={w.hardCapOnFail}
                  onChange={(e) => updateWeight(i, { hardCapOnFail: e.target.value })}
                />
                <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted-foreground">
                  <input
                    type="checkbox"
                    checked={w.isEnabled}
                    onChange={(e) => updateWeight(i, { isEnabled: e.target.checked })}
                  />
                  Enabled
                </label>
              </div>
            ))}
          </div>
        </div>

        {failure && <Alert tone="error">{failure}</Alert>}

        <div className="flex flex-wrap gap-2">
          <Button disabled={!canSubmit || create.isPending} onClick={submit}>
            {create.isPending ? 'Creating…' : 'Create draft version'}
          </Button>
          <Button variant="outline" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
