/** Next.js route/layout composition for (dashboard)/reports: page. */
import { ReportsQueueClient } from './ReportsQueueClient';

export const metadata = { title: 'Reports' };

export default function ReportsPage() {
  return <ReportsQueueClient />;
}
