import { redirect } from 'next/navigation';

/**
 * The notification template still sends /verify-email/{token}. The interactive
 * form reads ?token=, so normalize the emailed URL on the web app without
 * rebuilding the API/worker or changing already-issued links.
 */
export default async function EmailedVerifyLink({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  redirect(`/verify-email?token=${encodeURIComponent(token)}`);
}
