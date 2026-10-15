/** Privateaccountdetails module; defines PrivateAccountDetails. */
'use client';
import { useEffect, useState } from 'react';
import { useLocale } from 'next-intl';
import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import { toApiError } from '@trustlens/api-client';
import { Button, Card, CardHeader, CardTitle, CardContent, Alert } from '@trustlens/ui';
import { CityPicker } from '@/features/location';
import { PAKISTAN_PROVINCES, provinceOfCity, citiesInProvince } from '@trustlens/constants';
type Address = {
  id?: string | null;
  label: string;
  province: string;
  city: string;
  area: string;
  addressLine: string;
};
type Details = {
  dateOfBirth: string | null;
  gender: 'Woman' | 'Man' | 'Non-binary' | 'Self-described' | 'Prefer not to say' | null;
  addresses: Address[];
  version: number;
};
export function PrivateAccountDetails() {
  const ur = useLocale() === 'ur';
  const [draft, setDraft] = useState<Details | null>(null);
  const [saved, setSaved] = useState(false);
  const result = useQuery<Details>({
    queryKey: ['account', 'private-settings'],
    queryFn: async () => {
      const r = await api.GET('/api/v1/me/private-settings');
      if (r.error) throw toApiError(r.error);
      return (r.data as { data: Details }).data;
    },
  });
  useEffect(() => {
    if (result.data && draft === null) setDraft(result.data);
  }, [result.data, draft]);
  const mutation = useMutation({
    mutationFn: async () => {
      if (!draft) return;
      const r = await api.PUT('/api/v1/me/private-settings', { body: draft });
      if (r.error) throw toApiError(r.error);
      setDraft((r.data as { data: Details }).data);
      setSaved(true);
    },
  });
  const input = 'h-10 w-full rounded-lg border border-input bg-background px-3 text-sm';
  function update(next: Details) {
    setSaved(false);
    setDraft(next);
  }
  function address(i: number, next: Partial<Address>) {
    if (draft)
      update({
        ...draft,
        addresses: draft.addresses.map((a, n) => (n === i ? { ...a, ...next } : a)),
      });
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {ur ? 'نجی ذاتی معلومات اور پتے' : 'Private details & saved addresses'}
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {ur
            ? 'یہ اختیاری معلومات صرف آپ کو نظر آتی ہیں، عوامی پروفائل پر نہیں۔'
            : 'Optional information for your account. These details stay off your public profile and ads.'}
        </p>
      </CardHeader>
      <CardContent>
        {result.isPending ? (
          <p role="status">{ur ? 'لوڈ ہو رہا ہے…' : 'Loading…'}</p>
        ) : result.isError ? (
          <Alert tone="error">
            <p>{ur ? 'معلومات لوڈ نہیں ہوئیں۔' : 'Could not load your settings.'}</p>
            <Button variant="outline" onClick={() => void result.refetch()}>
              {ur ? 'دوبارہ کوشش' : 'Try again'}
            </Button>
          </Alert>
        ) : (
          draft && (
            <form
              className="space-y-5"
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate();
              }}
            >
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span>{ur ? 'تاریخ پیدائش (اختیاری)' : 'Date of birth (optional)'}</span>
                  <input
                    className={input}
                    type="date"
                    value={draft.dateOfBirth ?? ''}
                    min="1900-01-01"
                    max={new Date().toISOString().slice(0, 10)}
                    onChange={(e) => update({ ...draft, dateOfBirth: e.target.value || null })}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span>{ur ? 'صنف (اختیاری)' : 'Gender (optional)'}</span>
                  <select
                    className={input}
                    value={draft.gender ?? ''}
                    onChange={(e) =>
                      update({ ...draft, gender: (e.target.value || null) as Details['gender'] })
                    }
                  >
                    <option value="">{ur ? 'منتخب نہ کریں' : 'Not provided'}</option>
                    {['Woman', 'Man', 'Non-binary', 'Self-described', 'Prefer not to say'].map(
                      (x) => (
                        <option key={x}>{x}</option>
                      ),
                    )}
                  </select>
                </label>
              </div>
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">{ur ? 'محفوظ پتے' : 'Saved addresses'}</h3>
                <Button
                  type="button"
                  variant="outline"
                  disabled={draft.addresses.length >= 10 || mutation.isPending}
                  onClick={() =>
                    update({
                      ...draft,
                      addresses: [
                        ...draft.addresses,
                        { label: '', province: '', city: '', area: '', addressLine: '' },
                      ],
                    })
                  }
                >
                  {ur ? 'پتا شامل کریں' : 'Add address'}
                </Button>
              </div>
              {!draft.addresses.length && (
                <p className="text-sm text-muted-foreground">
                  {ur ? 'ابھی کوئی پتا محفوظ نہیں۔' : 'No saved addresses yet.'}
                </p>
              )}
              {draft.addresses.map((a, i) => (
                <fieldset
                  key={a.id ?? `new-${i}`}
                  disabled={mutation.isPending}
                  className="space-y-3 rounded-xl border border-border p-4"
                >
                  <legend className="px-1 text-sm">
                    {ur ? 'پتا' : 'Address'} {i + 1}
                  </legend>
                  <label className="block text-sm">
                    {ur ? 'نام' : 'Label'}
                    <input
                      required
                      maxLength={60}
                      className={input}
                      value={a.label}
                      placeholder={ur ? 'مثلاً گھر' : 'e.g. Home'}
                      onChange={(e) => address(i, { label: e.target.value })}
                    />
                  </label>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <AddressCity
                      value={a.city}
                      province={a.province}
                      onChange={(city, province) => address(i, { city, province })}
                    />
                    <label className="text-sm">
                      {ur ? 'علاقہ' : 'Area'}
                      <input
                        className={input}
                        maxLength={120}
                        value={a.area}
                        onChange={(e) => address(i, { area: e.target.value })}
                      />
                    </label>
                  </div>
                  <label className="block text-sm">
                    {ur ? 'مکمل پتا' : 'Full address'}
                    <input
                      required
                      minLength={5}
                      maxLength={300}
                      className={input}
                      value={a.addressLine}
                      onChange={(e) => address(i, { addressLine: e.target.value })}
                    />
                  </label>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() =>
                      update({ ...draft, addresses: draft.addresses.filter((_, n) => n !== i) })
                    }
                  >
                    {ur ? 'اس پتے کو ہٹائیں' : 'Remove this address'}
                  </Button>
                </fieldset>
              ))}
              {mutation.isError && <Alert tone="error">{mutation.error.message}</Alert>}
              {saved && (
                <p role="status" className="text-sm text-brand">
                  {ur ? 'نجی معلومات محفوظ ہو گئیں۔' : 'Private details saved.'}
                </p>
              )}
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending
                  ? ur
                    ? 'محفوظ ہو رہا ہے…'
                    : 'Saving…'
                  : ur
                    ? 'نجی معلومات محفوظ کریں'
                    : 'Save private details'}
              </Button>
            </form>
          )
        )}
      </CardContent>
    </Card>
  );
}
function AddressCity({
  value,
  province,
  onChange,
}: {
  value: string;
  province: string;
  onChange: (city: string, province: string) => void;
}) {
  const ur = useLocale() === 'ur';
  const region = province || provinceOfCity(value) || '';
  return (
    <div className="space-y-2">
      <label className="text-sm">
        {ur ? 'صوبہ' : 'Province'}
        <select
          className="h-10 w-full rounded-lg border border-input bg-background px-3"
          value={region}
          onChange={(e) => onChange('', e.target.value)}
        >
          <option value="">{ur ? 'صوبہ منتخب کریں' : 'Choose province'}</option>
          {Object.keys(PAKISTAN_PROVINCES).map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </label>
      <CityPicker
        cities={citiesInProvince(region)}
        value={value}
        onChange={(city) => onChange(city, region)}
        province={region}
        allowOther
      />
    </div>
  );
}
