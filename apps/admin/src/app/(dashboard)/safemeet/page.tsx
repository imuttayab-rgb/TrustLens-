/** Next.js route/layout composition for (dashboard)/safemeet: page. */
import { MeetingVenuesClient } from './MeetingVenuesClient';

export const metadata = { title: 'SafeMeet venues' };

export default function SafeMeetPage() {
  return <MeetingVenuesClient />;
}
