import { redirect } from 'next/navigation';

/** Accept the emailed /reset-password/{token} format as well as ?token=. */
export default async function EmailedResetLink({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  redirect(`/reset-password?token=${encodeURIComponent(token)}`);
}
