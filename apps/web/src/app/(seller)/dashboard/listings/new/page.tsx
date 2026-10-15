/** Next.js route/layout composition for (seller)/dashboard/listings/new: page. */
'use client';

import { PostAdWizard } from '@/features/listings';
import { Spinner } from '@trustlens/ui';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** `?listing=<id>` resumes a saved private draft in the wizard. */
function NewListingContent() {
  const params = useSearchParams();
  const raw = params.get('listing');
  const listingId = raw && UUID_RE.test(raw) ? raw : null;
  // key: switching drafts remounts the wizard with fresh state.
  return <PostAdWizard key={listingId ?? 'new'} initialListingId={listingId} />;
}

/** Post-an-Ad v2: the 4-step wizard (Details, Photos & Video, Location, Preview). */
export default function NewListingPage() {
  return (
    <Suspense fallback={<Spinner label="Loading..." />}>
      <NewListingContent />
    </Suspense>
  );
}
