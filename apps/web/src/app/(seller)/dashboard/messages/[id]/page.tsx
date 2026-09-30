import { redirect } from 'next/navigation';

/** Messages moved to `/messages/[id]` - see `/dashboard/messages`. */
export default async function ConversationRedirect({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const query = await searchParams;
  const intent = query.intent;
  const suffix = typeof intent === 'string' ? `?intent=${encodeURIComponent(intent)}` : '';
  redirect(`/messages/${id}${suffix}`);
}
