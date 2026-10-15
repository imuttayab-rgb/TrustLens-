/** Next.js route/layout composition for (public)/motors: page. */
import { MarketplaceHub } from '@/features/marketplace';
export const metadata = {
  title: 'Motors · TrustLens',
  description: 'Browse cars, bikes and vehicle parts on TrustLens.',
};
export default function MotorsPage() {
  return <MarketplaceHub kind="motors" />;
}
