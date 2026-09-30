import { redirect } from 'next/navigation';

/** Favourites moved to `/favourites`, in the public site's own chrome
 * (same reasoning as `/browse`: a buyer-facing surface, not a seller
 * dashboard one). This keeps the old bookmark/link working. */
export default function FavoritesRedirect() {
  redirect('/favourites');
}
