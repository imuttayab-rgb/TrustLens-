/** Next.js route/layout composition for (dashboard)/security: page. */
import { MfaSettings } from '@/features/mfa';

export const metadata = { title: 'Security' };

export default function SecurityPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-6 p-6 sm:p-8">
      <div>
        <h1 className="text-2xl font-bold">Security</h1>
        <p className="mt-1 text-muted-foreground">
          Two-factor authentication for your own account.
        </p>
      </div>
      <MfaSettings />
    </main>
  );
}
