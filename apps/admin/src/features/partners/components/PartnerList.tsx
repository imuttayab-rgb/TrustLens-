/** Reusable UI rendering and interaction component: PartnerList. */
'use client';

import { toApiError } from '@trustlens/api-client';
import { Alert, Button, Card, CardContent, Input, Spinner, cn } from '@trustlens/ui';
import { formatDateTime } from '@trustlens/utils';
import { useState } from 'react';
import {
  usePartnerKeys,
  usePartners,
  useRegisterPartner,
  useRevokeKey,
  useRotateKey,
  useScopes,
  useSetPartnerStatus,
  useIssueKey,
  type ApiKey,
  type IssuedKey,
  type Partner,
  type PartnerStatus,
} from '../hooks/use-partners';

const STATUS_TONE: Record<PartnerStatus, string> = {
  PENDING: 'text-risk-medium bg-risk-medium-bg',
  ACTIVE: 'text-risk-low bg-risk-low-bg',
  SUSPENDED: 'text-risk-high bg-risk-high-bg',
};

type Failure = { message: string; requestId?: string | undefined } | null;

/**
 * The plaintext key, shown once.
 *
 * Deliberately loud and deliberately blocking: it cannot be recovered, only
 * rotated, so a reviewer who closes this without copying has made work for
 * themselves and for the partner. The warning says exactly that rather than
 * a generic "keep this safe".
 */
function IssuedKeyPanel({ issued, onDismiss }: { issued: IssuedKey; onDismiss: () => void }) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="mt-4 rounded-lg border border-risk-medium/40 bg-risk-medium-bg/40 p-4">
      <p className="text-sm font-semibold">Copy this key now</p>
      <p className="mt-1 text-sm text-muted-foreground">
        This is the only time it is shown. Only a hash is stored, so it cannot be looked up later -
        a lost key has to be rotated.
      </p>

      <code className="mt-3 block break-all rounded-md bg-background/80 p-3 font-mono text-xs">
        {issued.plaintext}
      </code>

      <div className="mt-3 flex gap-2">
        <Button
          size="sm"
          onClick={() => {
            void navigator.clipboard.writeText(issued.plaintext).then(() => setCopied(true));
          }}
        >
          {copied ? 'Copied' : 'Copy key'}
        </Button>
        <Button size="sm" variant="outline" onClick={onDismiss}>
          I have saved it
        </Button>
      </div>
    </div>
  );
}

function KeyRow({ apiKey, clientId }: { apiKey: ApiKey; clientId: string }) {
  const rotate = useRotateKey(clientId);
  const revoke = useRevokeKey(clientId);
  const [issued, setIssued] = useState<IssuedKey | null>(null);
  const [confirmingRevoke, setConfirmingRevoke] = useState(false);
  const [failure, setFailure] = useState<Failure>(null);

  const dead = apiKey.state === 'revoked' || apiKey.state === 'expired';

  return (
    <li className="border-t border-border/60 py-3 first:border-t-0">
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{apiKey.name}</p>
          <p className="font-mono text-xs text-muted-foreground">{apiKey.keyPrefix}…</p>
        </div>

        <span
          className={cn(
            'rounded-full px-2 py-0.5 text-xs font-medium',
            dead ? 'bg-muted text-muted-foreground' : 'bg-risk-low-bg text-risk-low',
          )}
        >
          {apiKey.state}
        </span>

        <span className="text-xs text-muted-foreground">
          {apiKey.scopes.join(', ') || 'no scopes'}
        </span>

        {!dead && (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={rotate.isPending}
              onClick={() => {
                setFailure(null);
                rotate.mutate(apiKey.id, {
                  onSuccess: setIssued,
                  onError: (e) => setFailure(toApiError(e)),
                });
              }}
            >
              {rotate.isPending ? 'Rotating…' : 'Rotate'}
            </Button>

            {confirmingRevoke ? (
              <>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={revoke.isPending}
                  onClick={() => {
                    setFailure(null);
                    revoke.mutate(apiKey.id, {
                      onError: (e) => setFailure(toApiError(e)),
                    });
                  }}
                >
                  {revoke.isPending ? 'Revoking…' : 'Confirm'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setConfirmingRevoke(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              // Two steps on purpose: revocation is immediate and has no
              // overlap, so a misclick takes a live partner offline.
              <Button size="sm" variant="ghost" onClick={() => setConfirmingRevoke(true)}>
                Revoke
              </Button>
            )}
          </div>
        )}
      </div>

      <p className="mt-1 text-xs text-muted-foreground">
        Created {formatDateTime(apiKey.createdAt)}
        {apiKey.lastUsedAt ? ` · last used ${formatDateTime(apiKey.lastUsedAt)}` : ' · never used'}
      </p>

      {failure && (
        <Alert tone="error" className="mt-2" requestId={failure.requestId}>
          {failure.message}
        </Alert>
      )}

      {issued && <IssuedKeyPanel issued={issued} onDismiss={() => setIssued(null)} />}
    </li>
  );
}

function IssueKeyForm({ clientId, disabled }: { clientId: string; disabled: boolean }) {
  const issue = useIssueKey(clientId);
  const { data: scopes = [] } = useScopes();
  const [name, setName] = useState('');
  const [selected, setSelected] = useState<string[]>(['score:read']);
  const [issued, setIssued] = useState<IssuedKey | null>(null);
  const [failure, setFailure] = useState<Failure>(null);

  if (disabled) {
    return (
      <p className="mt-3 text-sm text-muted-foreground">
        Approve this partner before issuing a key — a key for an inactive partner would not
        authenticate.
      </p>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className="flex-1 text-sm">
          <label htmlFor={`key-name-${clientId}`} className="mb-1 block font-medium">
            New key name
          </label>
          <Input
            id={`key-name-${clientId}`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="production"
          />
        </div>

        <Button
          disabled={issue.isPending || name.trim().length === 0}
          onClick={() => {
            setFailure(null);
            issue.mutate(
              { name: name.trim(), scopes: selected, expiresInDays: null },
              {
                onSuccess: (data) => {
                  setIssued(data);
                  setName('');
                },
                onError: (e) => setFailure(toApiError(e)),
              },
            );
          }}
        >
          {issue.isPending ? 'Issuing…' : 'Issue key'}
        </Button>
      </div>

      <fieldset>
        <legend className="mb-1 text-sm font-medium">Scopes</legend>
        <div className="flex flex-wrap gap-3">
          {scopes.map((scope) => (
            <label key={scope} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={selected.includes(scope)}
                onChange={(e) =>
                  setSelected((prev) =>
                    e.target.checked ? [...prev, scope] : prev.filter((s) => s !== scope),
                  )
                }
              />
              <code className="text-xs">{scope}</code>
            </label>
          ))}
        </div>
        {selected.length === 0 && (
          // Allowed, and worth saying out loud: it authenticates and does
          // nothing, which looks like a broken key from the partner's side.
          <p className="mt-1 text-xs text-muted-foreground">
            A key with no scopes can sign in but call nothing.
          </p>
        )}
      </fieldset>

      {failure && (
        <Alert tone="error" requestId={failure.requestId}>
          {failure.message}
        </Alert>
      )}

      {issued && <IssuedKeyPanel issued={issued} onDismiss={() => setIssued(null)} />}
    </div>
  );
}

function PartnerRow({ partner }: { partner: Partner }) {
  const [expanded, setExpanded] = useState(false);
  const setStatus = useSetPartnerStatus();
  const { data: keys = [], isPending: keysLoading } = usePartnerKeys(expanded ? partner.id : null);
  const [failure, setFailure] = useState<Failure>(null);

  const changeStatus = (status: PartnerStatus) => {
    setFailure(null);
    setStatus.mutate(
      { clientId: partner.id, status },
      { onError: (e) => setFailure(toApiError(e)) },
    );
  };

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="min-w-0 flex-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-expanded={expanded}
          >
            <p className="font-medium">{partner.name}</p>
            <p className="text-xs text-muted-foreground">
              <code>{partner.slug}</code> · {partner.contactEmail}
            </p>
          </button>

          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              STATUS_TONE[partner.status],
            )}
          >
            {partner.status}
          </span>

          <div className="text-right text-xs text-muted-foreground">
            <p className="tabular-nums">
              {partner.usedThisMonth.toLocaleString()} / {partner.monthlyQuota.toLocaleString()}
            </p>
            <p>{partner.percentUsed}% of quota</p>
          </div>

          {partner.status === 'PENDING' && (
            <Button size="sm" onClick={() => changeStatus('ACTIVE')} disabled={setStatus.isPending}>
              Approve
            </Button>
          )}
          {partner.status === 'ACTIVE' && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => changeStatus('SUSPENDED')}
              disabled={setStatus.isPending}
            >
              Suspend
            </Button>
          )}
          {partner.status === 'SUSPENDED' && (
            <Button
              size="sm"
              variant="outline"
              onClick={() => changeStatus('ACTIVE')}
              disabled={setStatus.isPending}
            >
              Reinstate
            </Button>
          )}
        </div>

        {failure && (
          <Alert tone="error" className="mt-3" requestId={failure.requestId}>
            {failure.message}
          </Alert>
        )}

        {expanded && (
          <div className="mt-4 border-t border-border/60 pt-4">
            <h3 className="text-sm font-medium">Keys</h3>
            {keysLoading ? (
              <Spinner label="Loading keys" className="mt-3" />
            ) : keys.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">No keys issued yet.</p>
            ) : (
              <ul className="mt-2">
                {keys.map((k) => (
                  <KeyRow key={k.id} apiKey={k} clientId={partner.id} />
                ))}
              </ul>
            )}

            <IssueKeyForm clientId={partner.id} disabled={partner.status !== 'ACTIVE'} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RegisterPartnerForm() {
  const register = useRegisterPartner();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [email, setEmail] = useState('');
  const [quota, setQuota] = useState('10000');
  const [failure, setFailure] = useState<Failure>(null);

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Register a partner
      </Button>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="text-sm">
            <label htmlFor="partner-name" className="mb-1 block font-medium">
              Name
            </label>
            <Input
              id="partner-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Daraz"
            />
          </div>
          <div className="text-sm">
            <label htmlFor="partner-slug" className="mb-1 block font-medium">
              Slug
            </label>
            <Input
              id="partner-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="daraz"
              className="font-mono"
            />
          </div>
          <div className="text-sm">
            <label htmlFor="partner-email" className="mb-1 block font-medium">
              Contact email
            </label>
            <Input
              id="partner-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="api@daraz.pk"
            />
          </div>
          <div className="text-sm">
            <label htmlFor="partner-quota" className="mb-1 block font-medium">
              Monthly quota
            </label>
            <Input
              id="partner-quota"
              type="number"
              min={1}
              value={quota}
              onChange={(e) => setQuota(e.target.value)}
            />
          </div>
        </div>

        {failure && (
          <Alert tone="error" requestId={failure.requestId}>
            {failure.message}
          </Alert>
        )}

        <p className="text-xs text-muted-foreground">
          Registered as PENDING. Approve it before issuing a key.
        </p>

        <div className="flex gap-2">
          <Button
            disabled={register.isPending || !name.trim() || !slug.trim() || !email.trim()}
            onClick={() => {
              setFailure(null);
              register.mutate(
                {
                  name: name.trim(),
                  slug: slug.trim().toLowerCase(),
                  contactEmail: email.trim(),
                  monthlyQuota: Number(quota) || 10_000,
                },
                {
                  onSuccess: () => {
                    setOpen(false);
                    setName('');
                    setSlug('');
                    setEmail('');
                  },
                  onError: (e) => setFailure(toApiError(e)),
                },
              );
            }}
          >
            {register.isPending ? 'Registering…' : 'Register'}
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function PartnerList() {
  const { data: partners, isPending, error } = usePartners();

  if (isPending) return <Spinner label="Loading partners" />;

  if (error) {
    const failure = toApiError(error);
    return (
      <Alert tone="error" requestId={failure.requestId}>
        {failure.message}
      </Alert>
    );
  }

  return (
    <div className="space-y-4">
      <RegisterPartnerForm />

      {partners.length === 0 ? (
        <p className="text-sm text-muted-foreground">No partners registered yet.</p>
      ) : (
        <div className="space-y-3">
          {partners.map((p) => (
            <PartnerRow key={p.id} partner={p} />
          ))}
        </div>
      )}
    </div>
  );
}
