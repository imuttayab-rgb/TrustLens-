import Link from 'next/link';

/**
 * Shell for every signed-out screen.
 *
 * `min-h-dvh` rather than `min-h-screen`: on mobile Safari `100vh` counts the
 * area behind the browser chrome, so a centred form sits visibly too low and
 * the submit button can fall under the toolbar.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="px-6 py-5">
        <Link href="/" className="text-lg font-bold tracking-tight">
          TrustLens
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 pb-16">
        {children}
      </main>
    </div>
  );
}
