/** Next.js route/layout composition for (public)/profile/[reference]: page. */
import { PublicProfile } from '@/features/profile';
export const metadata = { title: 'Member profile | TrustLens' };
export default async function ProfilePage({ params }: { params: Promise<{ reference: string }> }) {
  const { reference } = await params;
  return <PublicProfile reference={reference} />;
}
