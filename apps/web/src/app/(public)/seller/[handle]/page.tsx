/** Next.js route/layout composition for (public)/seller/[handle]: page. */
import { redirect } from 'next/navigation';
export default async function LegacyProfile({ params }: { params: Promise<{ handle: string }> }) {
  const { handle } = await params;
  redirect(`/profile/${encodeURIComponent(handle)}`);
}
