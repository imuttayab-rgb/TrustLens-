/**
 * A plain link, not a fetch - clicking it must be a full top-level
 * navigation to the backend, which itself redirects on to Google. The
 * backend's /auth/google/callback sets the session cookie and redirects
 * back into the app; the existing session bootstrap (useSession ->
 * refreshSession) picks it up from there, so nothing here needs to know
 * what happens after the click.
 */
export function GoogleAuthButton({ label = 'Continue with Google' }: { label?: string }) {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

  return (
    <a
      href={`${apiBase}/api/v1/auth/google/login`}
      className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-md border border-input bg-background px-6 text-base font-medium transition-all duration-150 hover:scale-[1.01] hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:scale-[0.99]"
    >
      <svg className="h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M23.49 12.27c0-.79-.07-1.54-.19-2.27H12v4.51h6.47c-.29 1.48-1.14 2.73-2.4 3.58v3h3.86c2.26-2.09 3.56-5.17 3.56-8.82Z"
        />
        <path
          fill="#34A853"
          d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.86-3c-1.08.72-2.45 1.16-4.07 1.16-3.13 0-5.78-2.11-6.73-4.96H1.29v3.09C3.26 21.3 7.31 24 12 24Z"
        />
        <path
          fill="#FBBC05"
          d="M5.27 14.29a7.22 7.22 0 0 1 0-4.58V6.62H1.29a12 12 0 0 0 0 10.76l3.98-3.09Z"
        />
        <path
          fill="#EA4335"
          d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.94 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.62l3.98 3.09C6.22 6.86 8.87 4.75 12 4.75Z"
        />
      </svg>
      {label}
    </a>
  );
}
