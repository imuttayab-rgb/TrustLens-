'use client';
/** Recoverable admin route boundary; internal exception text stays out of the UI. */
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto max-w-lg p-8">
      <h1 className="text-xl font-semibold">This page could not load</h1>
      <p className="my-4">Please retry. Your saved records remain available.</p>
      <button className="rounded border p-3" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
