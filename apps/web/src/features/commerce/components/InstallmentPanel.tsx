/** Reusable UI rendering and interaction component: InstallmentPanel. */
'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Field } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import {
  useCancelInstallmentPlan,
  useCreateInstallmentPlan,
  useInstallmentPlan,
  usePayInstallment,
  type Installment,
} from '../hooks/use-commerce';

const FREQUENCY_OPTIONS = [
  { label: 'Weekly', days: 7 },
  { label: 'Every 2 weeks', days: 14 },
  { label: 'Monthly', days: 30 },
];

function formatMoney(amount: number, currency: string) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency }).format(amount);
  } catch {
    return `${currency} ${amount.toFixed(2)}`;
  }
}

/**
 * Buy-now-pay-later, sandboxed (PAY-01) - a payment *schedule* the platform
 * tracks, not a payment processor. Marking an installment paid is the same
 * mutual-trust confirmation "mark this deal done" already is: either party
 * can do it, there's no card to verify against.
 */
export function InstallmentPanel({
  transactionId,
  transactionAmount,
  currency,
  disabled,
}: {
  transactionId: string;
  transactionAmount: number;
  currency: string;
  disabled?: boolean;
}) {
  const { data: plan, isPending } = useInstallmentPlan(transactionId);
  const createPlan = useCreateInstallmentPlan();
  const payInstallment = usePayInstallment(transactionId);
  const cancelPlan = useCancelInstallmentPlan(transactionId);
  const [showForm, setShowForm] = useState(false);
  const [count, setCount] = useState(3);
  const [frequencyDays, setFrequencyDays] = useState(14);
  const [error, setError] = useState<string | null>(null);

  if (isPending) return null;

  async function handleCreate() {
    setError(null);
    try {
      await createPlan.mutateAsync({
        transactionId,
        installmentCount: count,
        frequencyDays,
      });
      setShowForm(false);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  async function handlePay(installmentId: string) {
    setError(null);
    try {
      await payInstallment.mutateAsync(installmentId);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  async function handleCancel() {
    if (!plan) return;
    setError(null);
    try {
      await cancelPlan.mutateAsync(plan.id);
    } catch (err) {
      setError(toApiError(err).message);
    }
  }

  if (!plan) {
    if (disabled) return null;
    return (
      <div className="border-t border-border/60 pt-2">
        {showForm ? (
          <div className="space-y-2 rounded-lg border border-border p-3 text-sm">
            <Field htmlFor="installment-count" label="Number of installments">
              <select
                id="installment-count"
                value={count}
                onChange={(event) => setCount(Number(event.target.value))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              >
                {Array.from({ length: 11 }, (_, i) => i + 2).map((n) => (
                  <option key={n} value={n}>
                    {n} payments of {formatMoney(transactionAmount / n, currency)}
                  </option>
                ))}
              </select>
            </Field>
            <Field htmlFor="installment-frequency" label="How often">
              <select
                id="installment-frequency"
                value={frequencyDays}
                onChange={(event) => setFrequencyDays(Number(event.target.value))}
                className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
              >
                {FREQUENCY_OPTIONS.map((option) => (
                  <option key={option.days} value={option.days}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            {error && <Alert tone="error">{error}</Alert>}
            <div className="flex gap-2">
              <Button size="sm" disabled={createPlan.isPending} onClick={() => void handleCreate()}>
                {createPlan.isPending ? 'Setting up…' : 'Set up plan'}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
            Pay in installments instead
          </Button>
        )}
      </div>
    );
  }

  const nextDue = plan.installments.find((i) => i.status !== 'PAID');

  return (
    <div className="space-y-2 border-t border-border/60 pt-2 text-sm">
      <p className="font-medium">
        Installment plan · {plan.installmentCount} payments · {plan.status.toLowerCase()}
      </p>
      <ul className="space-y-1">
        {plan.installments.map((installment: Installment) => (
          <li key={installment.id} className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">
              #{installment.sequenceNumber} · {formatMoney(installment.amount, plan.currency)} · due{' '}
              {formatDateTime(installment.dueAt)}
            </span>
            {installment.status === 'PAID' ? (
              <span className="text-xs text-risk-low">Paid</span>
            ) : (
              nextDue?.id === installment.id &&
              plan.status === 'ACTIVE' && (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={payInstallment.isPending}
                  onClick={() => void handlePay(installment.id)}
                >
                  Mark paid
                </Button>
              )
            )}
          </li>
        ))}
      </ul>
      {error && <Alert tone="error">{error}</Alert>}
      {plan.status === 'ACTIVE' && (
        <Button
          size="sm"
          variant="ghost"
          disabled={cancelPlan.isPending}
          onClick={() => void handleCancel()}
        >
          Cancel plan
        </Button>
      )}
    </div>
  );
}
