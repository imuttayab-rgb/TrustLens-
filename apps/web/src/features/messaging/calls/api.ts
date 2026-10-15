/** Bounded private call requests; auth and envelope errors are shared with other features. */
import { profileRequest } from '@/features/profile';
export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);
  try {
    return await profileRequest<T>(path, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timeout);
  }
}
