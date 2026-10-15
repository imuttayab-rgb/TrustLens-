'use client';
import { apiBase } from '@/features/profile';
import { getAccessToken, refreshSession, setAccessToken } from '@/lib/auth/session';

/** Download privately through the API; timeout includes reading the response body. */
export async function fetchVoiceBlob(path: string): Promise<Blob> {
  if (!path.startsWith('/me/chat-messages/') || !path.endsWith('/audio'))
    throw new Error('Invalid voice-message URL.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 45_000);
  const run = () => {
    const headers = new Headers();
    const token = getAccessToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    return fetch(`${apiBase}/api/v1${path}`, {
      headers,
      signal: controller.signal,
      credentials: 'include',
      cache: 'no-store',
    });
  };
  try {
    let response = await run();
    if (response.status === 401) {
      setAccessToken(await refreshSession());
      response = await run();
    }
    if (!response.ok)
      throw new Error(
        response.status === 403 || response.status === 404
          ? 'This voice message is no longer available to you.'
          : 'Could not load the voice message. Please retry.',
      );
    return await response.blob();
  } catch (error) {
    if (controller.signal.aborted) throw new Error('Audio download timed out. Please retry.');
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

export async function uploadVoice(
  conversationId: string,
  blob: Blob,
  clientId: string,
  onProgress: (percent: number) => void,
  replyToId?: string,
) {
  if (!getAccessToken()) setAccessToken(await refreshSession());
  const query = new URLSearchParams({ clientId });
  if (replyToId) query.set('replyToId', replyToId);
  const send = () =>
    new Promise<{
      status: number;
      data: { data?: unknown; detail?: string; error?: { message?: string } };
    }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${apiBase}/api/v1/me/conversations/${conversationId}/voice?${query}`);
      xhr.withCredentials = true;
      const token = getAccessToken();
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.setRequestHeader('Content-Type', blob.type || 'application/octet-stream');
      xhr.timeout = 120_000;
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onerror = xhr.ontimeout = () =>
        reject(new Error('Upload interrupted. Your recording is ready to retry.'));
      xhr.onload = () => {
        try {
          resolve({
            status: xhr.status,
            data: JSON.parse(xhr.responseText) as {
              data?: unknown;
              detail?: string;
              error?: { message?: string };
            },
          });
        } catch {
          reject(new Error('Upload failed. Your recording is ready to retry.'));
        }
      };
      xhr.send(blob);
    });
  let result = await send();
  if (result.status === 401) {
    setAccessToken(await refreshSession());
    result = await send();
  }
  if (result.status < 200 || result.status >= 300)
    throw new Error(
      result.status >= 500
        ? 'Upload interrupted. Your recording is ready to retry.'
        : (result.data.error?.message ??
            result.data.detail ??
            'Could not send the recording. Please retry.'),
    );
  return result.data.data;
}
