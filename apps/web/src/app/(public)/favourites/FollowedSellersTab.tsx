'use client';

import { useMyFollows } from '@/features/reputation';
import { Alert, Spinner } from '@trustlens/ui';
import { FollowedSellerRow } from './FollowedSellerRow';

export function FollowedSellersTab() {
  const { data: handles, isPending, isError } = useMyFollows();

  if (isPending) {
    return (
      <div className="flex justify-center py-16">
        <Spinner label="Loading followed sellers" />
      </div>
    );
  }

  if (isError) {
    return (
      <Alert tone="error" title="Could not load followed sellers">
        Try again in a moment.
      </Alert>
    );
  }

  if (handles.length === 0) {
    return (
      <Alert tone="info" title="Not following anyone yet">
        Follow a seller from their Trust Score page to see updates here.
      </Alert>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {handles.map((handle) => (
        <FollowedSellerRow key={handle} handle={handle} />
      ))}
    </div>
  );
}
