'use client';

import { Button, Card, CardContent } from '@trustlens/ui';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

export default function CheckPage() {
  const router = useRouter();
  const [handle, setHandle] = useState('');

  return (
    <main className="mx-auto max-w-xl px-6 py-20">
      <h1 className="text-3xl font-bold">Check a seller</h1>
      <p className="text-muted-foreground mt-2">
        Enter the seller&apos;s TrustLens handle to see their score and the reasons behind it.
      </p>

      <Card className="mt-8">
        <CardContent className="pt-6">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              const trimmed = handle.trim();
              if (trimmed) router.push(`/seller/${encodeURIComponent(trimmed)}`);
            }}
            className="flex gap-2"
          >
            <label htmlFor="handle" className="sr-only">
              Seller handle
            </label>
            <input
              id="handle"
              value={handle}
              onChange={(event) => setHandle(event.target.value)}
              placeholder="e.g. ayesha-traders"
              autoComplete="off"
              className="border-input focus-visible:ring-ring h-10 flex-1 rounded-md border px-3 focus-visible:outline-none focus-visible:ring-2"
            />
            <Button type="submit" disabled={!handle.trim()}>
              Check
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
