/** Next.js route/layout composition for (public)/property: page. */
import { MarketplaceHub } from '@/features/marketplace';
export const metadata = {
  title: 'Property · TrustLens',
  description: 'Browse property for sale and rent by city, area and budget.',
};
export default function PropertyPage() {
  return <MarketplaceHub kind="property" />;
}
