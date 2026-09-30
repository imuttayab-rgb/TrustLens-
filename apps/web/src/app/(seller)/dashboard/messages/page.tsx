import { redirect } from 'next/navigation';

/** Messages moved to `/messages`, in the public site's own chrome - same
 * reasoning as `/browse` and `/favourites`. Keeps the old bookmark working. */
export default function MessagesRedirect() {
  redirect('/messages');
}
