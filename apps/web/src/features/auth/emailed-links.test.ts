/** Regression coverage and test support for emailed links.test. */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));
vi.mock('next/navigation', () => ({ redirect }));

import EmailedResetLink from '../../app/(auth)/reset-password/[token]/page';
import EmailedVerifyLink from '../../app/(auth)/verify-email/[token]/page';

beforeEach(() => redirect.mockClear());

describe('links already issued by the notification worker', () => {
  it('routes /verify-email/{token} to the verification form', async () => {
    await EmailedVerifyLink({ params: Promise.resolve({ token: 'demo-token' }) });
    expect(redirect).toHaveBeenCalledWith('/verify-email?token=demo-token');
  });

  it('routes /reset-password/{token} to the password form', async () => {
    await EmailedResetLink({ params: Promise.resolve({ token: 'a+b/c' }) });
    expect(redirect).toHaveBeenCalledWith('/reset-password?token=a%2Bb%2Fc');
  });
});
