/* Only call invitations. No caching of authenticated pages, messages or audio. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('push', event => {
  let data;
  try { data = event.data.json(); } catch { return; }
  const uuid = /^[0-9a-f-]{36}$/i;
  if (!uuid.test(data.callId) || !uuid.test(data.conversationId)) return;
  const late = Date.now() - Date.parse(data.createdAt) > 45000;
  event.waitUntil(self.registration.showNotification(late ? 'Missed TrustLens call' : 'Incoming TrustLens call', {
    body: late ? 'Open your chat to call back.' : 'Tap to open TrustLens and answer if the call is still available.',
    tag: 'tl-call-' + data.callId,
    icon: '/call-icon.svg',
    data: { conversationId: data.conversationId },
    renotify: false,
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const id = event.notification.data?.conversationId;
  if (!/^[0-9a-f-]{36}$/i.test(id || '')) return;
  const url = new URL('/messages/' + id, self.location.origin).href;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const client = windows.find(item => new URL(item.url).origin === self.location.origin);
    if (client) { await client.navigate(url); await client.focus(); }
    else await self.clients.openWindow(url);
  })());
});
