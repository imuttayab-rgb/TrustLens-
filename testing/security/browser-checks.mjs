import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const artifactDir = resolve(process.env.AUDIT_OUT || './evidence');
fs.mkdirSync(artifactDir, { recursive: true });
process.env.TMPDIR = process.env.AUDIT_BROWSER_TMP || resolve(artifactDir, 'browser-temp');
fs.mkdirSync(process.env.TMPDIR, { recursive: true });
const root = resolve(process.env.TRUSTLENS_ROOT || '../TrustLens');
const require = createRequire(root + '/testing/e2e/package.json');
const { chromium: pw, expect } = require(process.env.AUDIT_PLAYWRIGHT || '@playwright/test');
const child = spawn(
  process.execPath,
  [
    root + '/apps/web/node_modules/next/dist/bin/next',
    'start',
    '--port',
    '3100',
    '--hostname',
    '127.0.0.1',
  ],
  {
    cwd: root + '/apps/web',
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
  },
);
let ready = false;
child.stdout.on('data', (d) => {
  process.stdout.write(d);
  if (d.toString().includes('Ready')) ready = true;
});
child.stderr.on('data', (d) => process.stderr.write(d));
child.on('exit', (code) => console.log('Next server exit', code));
for (let i = 0; i < 160 && !ready; i++) await new Promise((r) => setTimeout(r, 250));
const chromium = process.env.AUDIT_CHROMIUM_MODULE
  ? ((mod) => mod.default || mod)(require(process.env.AUDIT_CHROMIUM_MODULE))
  : null;
let browser;
try {
  browser = await pw.launch({
    executablePath: chromium ? await chromium.executablePath() : undefined,
    args: [
      ...(chromium ? chromium.args : []),
      '--no-proxy-server',
      '--use-fake-device-for-media-stream',
      '--use-fake-ui-for-media-stream',
    ],
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    permissions: ['microphone'],
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => {
    errors.push(e.message);
    console.log('PAGE ERROR', e.message);
  });
  page.on('console', (m) => {
    if (m.type() === 'error') console.log('BROWSER', m.text());
  });
  const buyer = '10000000-0000-0000-0000-000000000001',
    seller = '10000000-0000-0000-0000-000000000002',
    cid = '10000000-0000-0000-0000-000000000003';
  let messages = [
    {
      id: '10000000-0000-0000-0000-000000000004',
      conversationId: cid,
      senderId: buyer,
      body: 'Original test message',
      kind: 'text',
      createdAt: new Date().toISOString(),
      readAt: null,
      editableUntil: new Date(Date.now() + 60000).toISOString(),
      deleted: false,
    },
    {
      id: '10000000-0000-0000-0000-000000000005',
      conversationId: cid,
      senderId: seller,
      body: 'Earlier seller message',
      kind: 'text',
      createdAt: new Date(Date.now() - 120000).toISOString(),
      readAt: null,
      editableUntil: new Date(Date.now() - 60000).toISOString(),
      deleted: false,
    },
  ];
  let saved = [],
    closed = false,
    voiceUploads = 0,
    played = 0;
  let recorded = null;
  let uploadKeys = [];
  const conversation = () => ({
    id: cid,
    listingId: null,
    listingTitle: 'Test listing',
    counterpartName: 'Synthetic seller',
    counterpartUserId: seller,
    lastMessageAt: new Date().toISOString(),
    lastMessagePreview: 'Test message',
    unreadCount: 0,
    createdAt: new Date().toISOString(),
    muted: false,
    counterpartSellerHandle: null,
    counterpartRiskLevel: null,
    counterpartScore: null,
    serverNow: new Date().toISOString(),
    canSend: !closed,
    readOnly: closed,
    closesAt: closed ? new Date(Date.now() - 1000).toISOString() : null,
    listingStatus: closed ? 'SOLD' : 'ACTIVE',
  });
  await page.route('**/api/v1/**', async (route) => {
    const req = route.request(),
      url = new URL(req.url()),
      path = url.pathname.replace('/api/v1', ''),
      method = req.method();
    const reply = (data) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: {
          'access-control-allow-origin': 'http://127.0.0.1:3100',
          'access-control-allow-credentials': 'true',
        },
        body: JSON.stringify({ data }),
      });
    if (method === 'OPTIONS')
      return route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': 'http://127.0.0.1:3100',
          'access-control-allow-credentials': 'true',
          'access-control-allow-methods': 'GET,POST,PATCH,DELETE',
          'access-control-allow-headers': 'authorization,content-type',
        },
      });
    if (path === '/me')
      return reply({
        id: buyer,
        email: 'test@example.test',
        fullName: 'Test buyer',
        roles: ['BUYER'],
        permissions: [],
        status: 'ACTIVE',
      });
    if (path === '/auth/refresh') return reply({ accessToken: 'synthetic-ui-test' });
    if (path === '/me/profile')
      return reply({
        id: buyer,
        userId: buyer,
        username: 'testbuyer',
        publicName: 'Test buyer',
        displayName: 'Test buyer',
        handle: 'testbuyer',
        profileUrl: '/profile/testbuyer',
        photoUrl: null,
        photoMatched: true,
        nameVerified: true,
        score: null,
        riskLevel: null,
        verification: { identity: true, phone: true, email: true },
        canInteract: true,
        initialized: true,
      });
    if (path === '/me/conversations' && method === 'GET') return reply([conversation()]);
    if (path === `/me/conversations/${cid}`) return reply(conversation());
    if (path.endsWith('/timeline'))
      return reply({ items: messages, nextCursor: null, serverNow: new Date().toISOString() });
    if (path.endsWith('/clear/undo')) {
      messages = saved;
      return reply({});
    }
    if (path.endsWith('/clear')) {
      saved = messages;
      messages = [];
      return reply({
        undoToken: 'test-token',
        undoUntil: new Date(Date.now() + 10000).toISOString(),
      });
    }
    if (path.includes('/chat-messages/') && method === 'PATCH') {
      const b = req.postDataJSON();
      messages = messages.map((m) =>
        m.id === path.split('/')[3]
          ? { ...m, body: b.body, editedAt: new Date().toISOString() }
          : m,
      );
      return reply({});
    }
    if (path.includes('/chat-messages/') && method === 'DELETE') {
      messages = messages.map((m) =>
        m.id === path.split('/')[3] ? { ...m, body: 'This message was deleted', deleted: true } : m,
      );
      return reply({});
    }
    if (path.endsWith('/voice')) {
      voiceUploads++;
      uploadKeys.push(url.searchParams.get('clientId'));
      recorded = req.postDataBuffer();
      fs.writeFileSync(resolve(artifactDir, 'synthetic-recorded.webm'), recorded);
      if (voiceUploads === 1)
        return route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Synthetic upload interruption' }),
        });
      for (let n = 0; n < 2; n++)
        messages.push({
          id: 'voice-' + n,
          conversationId: cid,
          senderId: buyer,
          body: 'Voice message',
          kind: 'voice',
          createdAt: new Date().toISOString(),
          editableUntil: new Date(Date.now() + 60000).toISOString(),
          voice: { duration: 1.6, waveform: [0.2, 0.5, 0.8, 0.3, 0.6, 0.9, 0.2, 0.5] },
        });
      return reply({ conversationId: cid, message: { id: 'voice-0' } });
    }
    if (path.endsWith('/audio'))
      return route.fulfill({ status: 200, contentType: 'audio/webm', body: recorded });
    if (path.endsWith('/played')) {
      played++;
      return reply({ playedAt: new Date().toISOString() });
    }
    if (path.endsWith('/support')) return reply({ reportId: 'synthetic-support-case' });
    if (path === '/me/conversations' && method === 'POST') {
      const b = req.postDataJSON();
      messages.push({
        id: crypto.randomUUID(),
        conversationId: cid,
        senderId: buyer,
        body: b.body,
        kind: 'text',
        createdAt: new Date().toISOString(),
        editableUntil: new Date(Date.now() + 60000).toISOString(),
      });
      return reply({ conversationId: cid, message: messages.at(-1) });
    }
    if (path.includes('notification')) return reply([]);
    if (path.includes('categories') || path.includes('locations')) return reply([]);
    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Synthetic test route not used' }),
    });
  });
  const results = [];
  const check = (id, ok, observed) => results.push({ id, status: ok ? 'PASS' : 'FAIL', observed });
  const payloads = [
    '<img src=x onerror="window.__auditXss=1">',
    '<svg onload="window.__auditXss=2"></svg>',
    '<script>window.__auditXss=3</script>',
    'javascript:window.__auditXss=4',
  ];
  messages = payloads.map((body, i) => ({
    id: crypto.randomUUID(),
    conversationId: cid,
    senderId: seller,
    body,
    kind: 'text',
    createdAt: new Date(Date.now() - 120000).toISOString(),
    editableUntil: new Date(Date.now() - 60000).toISOString(),
    deleted: false,
  }));
  const response = await page.goto(`http://127.0.0.1:3100/messages/${cid}`);
  for (const [i, payload] of payloads.entries()) {
    await expect(page.getByText(payload, { exact: true })).toBeVisible();
    check(
      'chat-xss-' + i,
      await page.evaluate(() => !window.__auditXss),
      'stored API payload rendered as text; no execution',
    );
  }
  check(
    'access-token-not-browser-storage',
    await page.evaluate(
      () => !JSON.stringify({ ...localStorage, ...sessionStorage }).includes('synthetic-ui-test'),
    ),
    'synthetic bearer absent from localStorage/sessionStorage',
  );
  const headers = response.headers();
  check(
    'web-local-csp',
    !!headers['content-security-policy'] && !headers['strict-transport-security'],
    {
      csp: headers['content-security-policy'] || null,
      hsts: headers['strict-transport-security'] || null,
      nosniff: headers['x-content-type-options'],
      frame: headers['x-frame-options'],
    },
  );
  for (const path of ['/.env', '/.env.production', '/.git/config', '/openapi.json', '/docs']) {
    const r = await fetch('http://127.0.0.1:3100' + path);
    check('web-hidden-' + path, r.status === 404, { status: r.status });
  }
  check(
    'nonce-scripts-hydrate',
    (await page.locator('script[nonce]').count()) > 0 && errors.length === 0,
    { nonceScripts: await page.locator('script[nonce]').count(), errors },
  );
  fs.writeFileSync(resolve(artifactDir, 'browser-results.json'), JSON.stringify(results, null, 2));
  console.log(JSON.stringify(results, null, 2));
} finally {
  if (browser) await browser.close();
  child.kill('SIGTERM');
}
