'use client';

import { ListingForm, useCreateListing } from '@/features/listings';
import Link from 'next/link';

export default function NewListingPage() {
  const create = useCreateListing();

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/dashboard/listings" className="text-sm text-muted-foreground hover:underline">
        ← Back to listings
      </Link>
      <h1 className="mt-2 text-2xl font-bold">Add a listing</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        It will be checked for scam patterns as soon as you save it.
      </p>

      <div className="mt-8">
        <ListingForm
          onSubmit={(payload) => create.mutateAsync(payload)}
          submitLabel="Save listing"
        />
      </div>
    </div>
  );
}
