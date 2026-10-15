/** Next.js route/layout composition for (seller)/dashboard/listings: page. */
'use client';
import { OwnerAds } from '@/features/profile';
import { PublicationNotice } from '@/features/listings';
export default function ListingsPage() {
  return (
    <div className="space-y-5">
      <PublicationNotice />
      <OwnerAds />
    </div>
  );
}
