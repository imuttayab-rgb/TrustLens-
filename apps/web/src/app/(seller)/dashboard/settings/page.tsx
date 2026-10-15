/** Next.js route/layout composition for (seller)/dashboard/settings: page. */
'use client';

import { api } from '@/lib/api/client';
import { PrivateAccountDetails } from '@/features/account';
import { setAccessToken } from '@/lib/auth/session';
import { useApiForm } from '@/lib/forms/use-api-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toApiError } from '@trustlens/api-client';
import {
  Alert,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Field,
  Input,
  Spinner,
} from '@trustlens/ui';
import { formatDistanceToNow } from 'date-fns';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

const passwordSchema = z.object({
  currentPassword: z.string().min(1, 'Current password is required'),
  newPassword: z.string().min(12, 'Password must be at least 12 characters'),
});

const deleteSchema = z.object({
  password: z.string().min(1, 'Password is required to delete your account'),
});

const sessionsSchema = z.array(
  z.object({
    id: z.string(),
    createdAt: z.string(),
    userAgent: z.string().nullable(),
    ipAddress: z.string().nullable(),
    isCurrent: z.boolean(),
  }),
);

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const router = useRouter();

  // Sessions Query
  const { data: sessions, isPending: sessionsLoading } = useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: async () => {
      const result = await api.GET('/api/v1/auth/sessions');
      if (result.error) throw toApiError(result.error);
      return sessionsSchema.parse(result.data?.data);
    },
  });

  // Revoke Session Mutation
  const revokeSession = useMutation({
    mutationFn: async (sessionId: string) => {
      const result = await api.DELETE('/api/v1/auth/sessions/{session_id}', {
        params: { path: { session_id: sessionId } },
      });
      if (result.error) throw toApiError(result.error);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['auth', 'sessions'] });
    },
  });

  // Password Change Form
  const pwForm = useForm<z.infer<typeof passwordSchema>>({
    resolver: zodResolver(passwordSchema),
  });
  const pwApi = useApiForm(pwForm.setError);
  const onPasswordSubmit = pwForm.handleSubmit(async (values) => {
    const ok = await pwApi.submit(async () => {
      const result = await api.POST('/api/v1/auth/change-password', {
        body: { currentPassword: values.currentPassword, newPassword: values.newPassword },
      });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) {
      pwForm.reset();
      void queryClient.invalidateQueries({ queryKey: ['auth', 'sessions'] });
      alert('Password changed successfully. Other sessions have been signed out.');
    }
  });

  // Export Data
  const exportData = useMutation({
    mutationFn: async () => {
      const result = await api.GET('/api/v1/auth/me/export');
      if (result.error) throw toApiError(result.error);

      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `trustlens-export-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      window.URL.revokeObjectURL(url);
    },
  });

  // Delete Account Form
  const delForm = useForm<z.infer<typeof deleteSchema>>({
    resolver: zodResolver(deleteSchema),
  });
  const delApi = useApiForm(delForm.setError);
  const onDeleteSubmit = delForm.handleSubmit(async (values) => {
    if (
      !confirm(
        'Deactivate your account, hide your ads and request data deletion? You will be signed out. Data erasure requires staff review.',
      )
    ) {
      return;
    }
    const ok = await delApi.submit(async () => {
      const result = await api.DELETE('/api/v1/auth/me', {
        body: { password: values.password },
      });
      if (result.error) throw toApiError(result.error);
    });
    if (ok) {
      setAccessToken(null);
      queryClient.clear();
      router.push('/login?account=deactivated');
    }
  });

  return (
    <div className="mx-auto max-w-2xl space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-bold">Account Settings</h1>
        <p className="text-muted-foreground">Manage your security and data.</p>
      </div>

      <PrivateAccountDetails />
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>
            Changing your password will sign you out of all other devices.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(e) => void onPasswordSubmit(e)} className="space-y-4">
            <Field
              htmlFor="currentPassword"
              label="Current password"
              error={pwForm.formState.errors.currentPassword?.message}
            >
              <Input type="password" {...pwForm.register('currentPassword')} />
            </Field>
            <Field
              htmlFor="newPassword"
              label="New password"
              error={pwForm.formState.errors.newPassword?.message}
            >
              <Input type="password" {...pwForm.register('newPassword')} />
            </Field>
            {pwApi.formError && <Alert tone="error">{pwApi.formError.message}</Alert>}
            <Button type="submit" disabled={pwForm.formState.isSubmitting}>
              {pwForm.formState.isSubmitting ? 'Changing...' : 'Change Password'}
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Sessions</CardTitle>
          <CardDescription>Devices currently signed in to your account.</CardDescription>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <Spinner />
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border">
              {sessions?.map((session) => (
                <li key={session.id} className="flex items-center justify-between p-4">
                  <div>
                    <p className="font-medium">
                      {session.userAgent || 'Unknown device'}
                      {session.isCurrent && (
                        <span className="ml-2 rounded bg-primary/10 px-2 py-0.5 text-xs text-primary">
                          This device
                        </span>
                      )}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      IP: {session.ipAddress || 'Unknown'} · Signed in{' '}
                      {formatDistanceToNow(new Date(session.createdAt))} ago
                    </p>
                  </div>
                  {!session.isCurrent && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => revokeSession.mutate(session.id)}
                      disabled={revokeSession.isPending}
                    >
                      Sign out
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data & Privacy</CardTitle>
          <CardDescription>
            Download a copy of your data or permanently delete your account.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <h3 className="font-medium">Export Data</h3>
            <p className="mb-3 text-sm text-muted-foreground">
              Download a machine-readable (JSON) archive of your account data and seller profile.
            </p>
            <Button
              variant="outline"
              onClick={() => exportData.mutate()}
              disabled={exportData.isPending}
            >
              {exportData.isPending ? 'Preparing export...' : 'Export Data'}
            </Button>
          </div>

          <div className="border-t border-border pt-6">
            <h3 className="font-medium text-destructive">Delete Account</h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Deactivate your account and hide your ads immediately. Data deletion is recorded for
              staff review; stored records are not automatically erased. Google-only users must set
              a password using Forgot password before confirming.
            </p>
            <form onSubmit={(e) => void onDeleteSubmit(e)} className="space-y-4">
              <Field
                htmlFor="password"
                label="Confirm password to delete"
                error={delForm.formState.errors.password?.message}
              >
                <Input type="password" {...delForm.register('password')} />
              </Field>
              {delApi.formError && <Alert tone="error">{delApi.formError.message}</Alert>}
              <Button type="submit" variant="destructive" disabled={delForm.formState.isSubmitting}>
                {delForm.formState.isSubmitting
                  ? 'Submitting...'
                  : 'Deactivate and Request Deletion'}
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
