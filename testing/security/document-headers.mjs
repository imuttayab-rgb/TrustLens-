/** Verify hosted header configuration locally; this never deploys anything. */
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';
import fs from 'node:fs';
const root = resolve(process.env.TRUSTLENS_ROOT || '.');
const out = resolve(process.env.AUDIT_OUT || 'security-evidence');
fs.mkdirSync(out, { recursive: true });
const results = [];
for (const [app, port] of [
  ['web', 3104],
  ['admin', 3105],
]) {
  const child = spawn(
    process.execPath,
    [
      `${root}/apps/${app}/node_modules/next/dist/bin/next`,
      'start',
      '--port',
      String(port),
      '--hostname',
      '127.0.0.1',
    ],
    {
      cwd: `${root}/apps/${app}`,
      env: {
        ...process.env,
        NEXT_TELEMETRY_DISABLED: '1',
        CSP_APP_ORIGIN: `https://${app}.example`,
        CSP_API_ORIGIN: 'https://api.example',
        CSP_MEDIA_ORIGIN: 'wss://calls.example',
        CSP_CONNECT_ORIGINS: 'https://objects.example',
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  );
  let ready = false;
  child.stdout.on('data', (data) => {
    if (data.toString().includes('Ready')) ready = true;
  });
  child.stderr.on('data', () => {});
  try {
    for (let i = 0; i < 100 && !ready; i++) await new Promise((done) => setTimeout(done, 100));
    if (!ready) throw new Error(`${app} did not start`);
    const first = await fetch(`http://127.0.0.1:${port}/login`, {
      headers: { 'x-nonce': 'attacker-controlled' },
    });
    const second = await fetch(`http://127.0.0.1:${port}/login`);
    const policy = first.headers.get('content-security-policy') || '';
    const html = await first.text();
    const nonce = /nonce-([^']+)/.exec(policy)?.[1];
    const checks = {
      csp:
        policy.includes("'strict-dynamic'") &&
        !policy.includes("script-src 'self' 'unsafe-inline'") &&
        !policy.includes('localhost'),
      hsts: first.headers.get('strict-transport-security')?.includes('31536000'),
      nonce:
        !!nonce &&
        nonce !== 'attacker-controlled' &&
        html.includes(`nonce="${nonce}"`) &&
        policy !== second.headers.get('content-security-policy'),
      explicitOrigins:
        policy.includes('https://api.example') &&
        policy.includes('wss://calls.example') &&
        policy.includes('https://objects.example'),
    };
    for (const [name, ok] of Object.entries(checks))
      results.push({ id: `${app}-${name}`, status: ok ? 'PASS' : 'FAIL' });
  } finally {
    child.kill('SIGTERM');
  }
}
fs.writeFileSync(resolve(out, 'document-header-results.json'), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results));
if (results.some((item) => item.status !== 'PASS')) process.exitCode = 1;
