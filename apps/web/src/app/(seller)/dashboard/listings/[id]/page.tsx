'use client';

import { StartAuctionCard } from '@/features/commerce';
import {
  ListingForm,
  ListingImages,
  ListingRiskPanel,
  useAnalyseListing,
  useDeleteListing,
  useListing,
  useUpdateListing,
} from '@/features/listings';
import { Alert, Button, Card, CardContent, CardHeader, CardTitle, Spinner } from '@trustlens/ui';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useState } from 'react';

export default function ListingDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const { data: listing, isPending } = useListing(id);
  const update = useUpdateListing(id);
  const remove = useDeleteListing();
  const analyse = useAnalyseListing();
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  if (isPending) {
    return (
      <div className="flex min-h-[40dvh] items-center justify-center">
        <Spinner label="Loading" />
      </div>
    );
  }

  if (!listing) {
    return <Alert tone="error" title="This item could not be found." />;
  }

  const removed = listing.status === 'REMOVED';

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/dashboard/listings" className="text-sm text-muted-foreground hover:underline">
        ← Back to selling
      </Link>
      <h1 className="mt-2 truncate text-2xl font-bold">{listing.title}</h1>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Risk analysis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ListingRiskPanel analysis={listing.analysis} status={listing.status} />
          <Button
            variant="outline"
            className="w-full"
            disabled={analyse.isPending || listing.status === 'ANALYSING'}
            onClick={() => analyse.mutate(id)}
          >
            {analyse.isPending ? 'Queueing…' : 'Re-run the analysis'}
          </Button>
        </CardContent>
      </Card>

      {!removed && (
        <StartAuctionCard
          listingId={id}
          listingStatus={listing.status}
          suggestedPrice={listing.price}
          currency={listing.currency}
        />
      )}

      {removed ? (
        <Alert tone="warning" title="This item has been removed" className="mt-6">
          Removed listings are kept so the Trust Score they contributed to can still be explained
          and appealed. They can no longer be edited.
        </Alert>
      ) : (
        <>
          <div className="mt-10">
            <ListingImages listingId={id} />
          </div>

          <h2 className="mt-10 text-lg font-semibold">Edit</h2>
          <div className="mt-4">
            <ListingForm
              listing={listing}
              onSubmit={(payload) => update.mutateAsync(payload)}
              submitLabel="Save changes"
            />
          </div>

          <div className="mt-10 border-t border-border pt-6">
            {confirmingDelete ? (
              <div className="space-y-3">
                <Alert tone="warning" title="Remove this item?">
                  Your Trust Score will be recalculated without it.
                </Alert>
                <div className="flex gap-2">
                  <Button
                    variant="destructive"
                    disabled={remove.isPending}
                    onClick={() =>
                      remove.mutate(id, {
                        onSuccess: () => {
                          router.push('/dashboard/listings');
                          router.refresh();
                        },
                      })
                    }
                  >
                    {remove.isPending ? 'Removing…' : 'Yes, remove it'}
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmingDelete(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="ghost" onClick={() => setConfirmingDelete(true)}>
                Remove this item
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}
