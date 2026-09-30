import { redirect } from 'next/navigation';

/** Messages moved to `/messages/new` - see `/dashboard/messages`. */
export default async function NewConversationRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = await searchParams;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (typeof value === 'string') params.set(key, value);
  }
  const qs = params.toString();
  redirect(`/messages/new${qs ? `?${qs}` : ''}`);
}
