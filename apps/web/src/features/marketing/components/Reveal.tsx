'use client';

import { stagger, useInView, usePrefersReducedMotion } from '@/lib/motion';
import { cn } from '@trustlens/ui';

/**
 * Reveals its children when they first scroll into view.
 *
 * The hidden state is applied only after we know motion is allowed and an
 * observer exists. Anything else risks content that never appears — an
 * animation failing should cost polish, never legibility.
 */
export function Reveal({
  children,
  className,
  delayMs = 0,
  as: Tag = 'div',
}: {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  as?: 'div' | 'section' | 'li';
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  const reduced = usePrefersReducedMotion();
  const animate = !reduced;

  return (
    <Tag
      ref={ref as never}
      style={animate && inView ? stagger(0, 0, delayMs) : undefined}
      className={cn(className, animate && (inView ? 'animate-fade-up' : 'opacity-0'))}
    >
      {children}
    </Tag>
  );
}
