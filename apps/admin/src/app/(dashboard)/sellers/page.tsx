import { SellerList } from '@/features/sellers';

export const metadata = { title: 'Sellers' };

export default function SellersPage() {
  return (
    <main className="mx-auto max-w-6xl p-6 sm:p-8">
      <h1 className="text-2xl font-bold">Sellers</h1>
      <p className="mt-1 text-muted-foreground">
        Search by name, handle or email. Filter by risk band or flag status.
      </p>
      <SellerList />
    </main>
  );
}
