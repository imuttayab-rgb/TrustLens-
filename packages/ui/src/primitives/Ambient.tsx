import { cn } from '../lib/cn';

/**
 * The shared background wash.
 *
 * One component so every surface drifts at the same rate and the product
 * feels like a single place. `subtle` is for screens people work in — the
 * dashboard, the review queue — where full-strength light would compete with
 * a score gauge or a risk badge for attention.
 *
 * Purely decorative and always `aria-hidden`.
 */
export function Ambient({
  intensity = 'subtle',
  className,
}: {
  intensity?: 'subtle' | 'full';
  className?: string;
}) {
  const full = intensity === 'full';

  return (
    <div aria-hidden="true" className={cn('pointer-events-none absolute inset-0 -z-10', className)}>
      <div
        className={cn(
          'animate-drift absolute rounded-full blur-[120px]',
          full
            ? 'bg-brand/[0.13] -top-40 -left-32 h-[34rem] w-[34rem]'
            : 'bg-brand/[0.07] -top-52 -left-40 h-[30rem] w-[30rem]',
        )}
      />
      <div
        className={cn(
          'animate-drift absolute rounded-full blur-[120px]',
          full
            ? 'bg-brand-2/[0.11] -top-24 right-[-10rem] h-[30rem] w-[30rem]'
            : 'bg-brand-2/[0.06] -top-32 right-[-12rem] h-[26rem] w-[26rem]',
        )}
        style={{ animationDelay: '-11s' }}
      />
      {/* Hairline grid fading out downward — gives the dark field a surface
          without ever becoming a pattern. */}
      <div
        className={cn(
          'absolute inset-0 bg-[size:56px_56px]',
          'bg-[linear-gradient(hsl(var(--border)/0.5)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--border)/0.5)_1px,transparent_1px)]',
          full
            ? '[mask-image:radial-gradient(ellipse_75%_55%_at_50%_0%,#000_35%,transparent_100%)]'
            : '[mask-image:radial-gradient(ellipse_60%_40%_at_50%_0%,#000_10%,transparent_85%)]',
        )}
      />
    </div>
  );
}
