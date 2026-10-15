import { redirect } from 'next/navigation';
/** There is no overview page at `/dashboard/verification`; the real steps are
 * identity, phone, email and business. Any old or hand-typed link to the bare
 * path lands on the identity step instead of a 404. */
export default function VerificationIndexRedirect() {
  redirect('/dashboard/verification/identity');
}
