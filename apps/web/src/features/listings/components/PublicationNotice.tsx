'use client';

import { useMyProfile } from '@/features/profile';
import { useSeller } from '@/features/seller';
import { Alert } from '@trustlens/ui';
import Link from 'next/link';

/**
 * A progress explanation, not a security control. The backend publication
 * policy and public SQL queries enforce this even for direct API requests.
 */
export function PublicationNotice() {
  const { data: seller } = useSeller();
  const { data: profile } = useMyProfile();
  if (!seller) return null;

  const checks = [
    {
      ready: Boolean(profile?.canInteract),
      label: 'Confirm your ID-matched name and approved profile photo',
      href: '/dashboard',
    },
    {
      ready: seller.identityStatus === 'VERIFIED',
      label: 'Complete live ID/face verification and wait for a human reviewer',
      href: '/dashboard/verification/identity',
    },
    {
      ready: seller.phoneStatus === 'VERIFIED',
      label: 'Verify your phone number',
      href: '/dashboard/verification/phone',
    },
    {
      ready: seller.emailStatus === 'VERIFIED',
      label: 'Confirm your email address',
      href: '/dashboard/verification/email',
    },
  ];
  const missing = checks.filter((check) => !check.ready);
  if (missing.length === 0 && !seller.isFlagged) return null;

  return (
    <Alert tone="warning" title="Your listing is not live yet">
      <p>
        You can save and edit your listing now. Buyers will not see it until seller verification and
        the listing safety check are complete. A 100/100 Trust Score is not required.
      </p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {missing.map(({ label, href }) => (
          <li key={href}>
            <Link href={href} className="font-medium underline underline-offset-2">
              {label}
            </Link>
          </li>
        ))}
        {seller.isFlagged && <li>A safety flag needs staff review before you can sell.</li>}
      </ul>
    </Alert>
  );
}
