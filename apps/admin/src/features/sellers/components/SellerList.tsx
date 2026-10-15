/** Reusable UI rendering and interaction component: SellerList. */
'use client';

import { useSellerSearch, type SellerRisk, type SellerSearchParams } from '@/features/sellers';
import { Alert, Card, CardContent, Input, Spinner } from '@trustlens/ui';
import Link from 'next/link';
import { useState } from 'react';

const risks: Array<SellerRisk | 'ALL'> = ['ALL', 'LOW', 'MEDIUM', 'HIGH', 'UNKNOWN'];

const statusLabel = (value: string) => value.replaceAll('_', ' ');

export function SellerList() {
  const [filters, setFilters] = useState<SellerSearchParams>({
    search: '',
    riskLevel: 'ALL',
    flagged: 'ALL',
    page: 1,
  });
  const { data, error, isPending, isFetching } = useSellerSearch(filters);
  const pagination = data?.meta.pagination;

  function updateFilters(next: Partial<SellerSearchParams>) {
    setFilters((current) => ({ ...current, ...next, page: next.page ?? 1 }));
  }

  return (
    <section className="mt-8 space-y-4">
      <div className="grid gap-3 rounded-lg border border-border/70 bg-card/50 p-4 md:grid-cols-[1fr_auto_auto]">
        <Input
          value={filters.search}
          onChange={(event) => updateFilters({ search: event.target.value })}
          placeholder="Search name, handle or email"
          aria-label="Search sellers"
        />
        <select
          value={filters.riskLevel}
          onChange={(event) =>
            updateFilters({ riskLevel: event.target.value as SellerRisk | 'ALL' })
          }
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Filter by risk level"
        >
          {risks.map((risk) => (
            <option key={risk} value={risk}>
              {risk === 'ALL' ? 'All risk levels' : risk}
            </option>
          ))}
        </select>
        <select
          value={filters.flagged}
          onChange={(event) =>
            updateFilters({ flagged: event.target.value as SellerSearchParams['flagged'] })
          }
          className="h-10 rounded-md border border-input bg-background px-3 text-sm"
          aria-label="Filter by flag status"
        >
          <option value="ALL">All flags</option>
          <option value="TRUE">Flagged only</option>
          <option value="FALSE">Not flagged</option>
        </select>
      </div>

      {error && <Alert tone="error">Unable to load sellers. Please try again.</Alert>}
      {isPending ? (
        <div className="flex justify-center py-12">
          <Spinner label="Loading sellers" />
        </div>
      ) : data && data.data.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            No sellers match these filters.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-border/70 bg-muted/30 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">Seller</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="px-4 py-3 font-medium">Risk</th>
                  <th className="px-4 py-3 font-medium">Verification</th>
                  <th className="px-4 py-3 font-medium">Flag</th>
                </tr>
              </thead>
              <tbody className={isFetching ? 'opacity-60' : undefined}>
                {data?.data.map((seller) => (
                  <tr
                    key={seller.id}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/20"
                  >
                    <td className="px-4 py-4">
                      <Link
                        href={`/sellers/${seller.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {seller.displayName}
                      </Link>
                      <p className="mt-1 text-xs text-muted-foreground">
                        @{seller.handle} · {seller.email}
                      </p>
                    </td>
                    <td className="px-4 py-4 font-semibold tabular-nums">
                      {seller.score ?? '—'}
                      <span className="text-xs font-normal text-muted-foreground"> / 100</span>
                    </td>
                    <td className="px-4 py-4">{seller.riskLevel ?? 'UNKNOWN'}</td>
                    <td className="px-4 py-4 text-xs text-muted-foreground">
                      ID {statusLabel(seller.identityStatus)}
                      <br />
                      Phone {statusLabel(seller.phoneStatus)}
                      <br />
                      Email {statusLabel(seller.emailStatus)}
                    </td>
                    <td className="px-4 py-4">{seller.isFlagged ? 'Flagged' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {pagination && pagination.totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {pagination.total} sellers · page {pagination.page} of {pagination.totalPages}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!pagination.hasPrev}
              onClick={() => setFilters((current) => ({ ...current, page: current.page - 1 }))}
              className="rounded-md border px-3 py-2 disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={!pagination.hasNext}
              onClick={() => setFilters((current) => ({ ...current, page: current.page + 1 }))}
              className="rounded-md border px-3 py-2 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
