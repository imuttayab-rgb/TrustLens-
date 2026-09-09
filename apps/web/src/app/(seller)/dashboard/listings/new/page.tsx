'use client';

import { ListingForm, ListingImages, useCreateListing, type Listing } from '@/features/listings';
import { Button } from '@trustlens/ui';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export default function NewListingPage() {
  const router = useRouter();
  const create = useCreateListing();
  const [created, setCreated] = useState<Listing | null>(null);

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/dashboard/listings" className="text-sm text-muted-foreground hover:underline">
        ← Back to selling
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Sell something</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        {created
          ? 'Add photos so buyers can trust what they see. Good photos raise your Trust Score.'
          : 'It will be checked for scam patterns as soon as you save it.'}
      </p>

      <div className="mt-8">
        {created ? (
          <div className="space-y-8">
            <ListingImages listingId={created.id} />
            <Button
              size="lg"
              className="w-full"
              onClick={() => {
                router.push(`/dashboard/listings/${created.id}`);
                router.refresh();
              }}
            >
              Finish
            </Button>
          </div>
        ) : (
          <ListingForm
            onSubmit={(payload) => create.mutateAsync(payload)}
            submitLabel="Continue to photos"
            onSuccess={(listing) => setCreated(listing)}
          />
        )}
      </div>
    </div>
  );
}
