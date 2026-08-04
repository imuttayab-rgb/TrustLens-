'use client';

import { useEffect, useRef, useState } from 'react';

/** True when the visitor has asked the OS to reduce motion. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(query.matches);
    const onChange = (event: MediaQueryListEvent) => setReduced(event.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);

  return reduced;
}

/**
 * Fires once when an element first enters the viewport.
 *
 * Once, deliberately: an animation that replays every time you scroll past it
 * stops reading as arrival and starts reading as a glitch.
 */
export function useInView<T extends HTMLElement>(rootMargin = '-12% 0px') {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    // Without IntersectionObserver, show everything rather than nothing.
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin, threshold: 0.15 },
    );
    observer.observe(node);

    // Safety net. Callers hide content until this fires, so anything that
    // stops the observer reporting - a background tab, a pane that is not
    // compositing, a headless renderer - would otherwise leave the page
    // permanently blank. Revealing late is a cosmetic failure; never
    // revealing is a broken page.
    const fallback = setTimeout(() => setInView(true), 1200);

    return () => {
      clearTimeout(fallback);
      observer.disconnect();
    };
  }, [rootMargin]);

  return { ref, inView } as const;
}

/**
 * Counts from 0 to `target` once `active` is true.
 *
 * Eased rather than linear, so the number decelerates into its final value -
 * a linear count reads like a loading spinner, an eased one reads like a
 * measurement settling.
 *
 * Reduced motion jumps straight to the answer: the number IS the content, so
 * it must never be withheld for the sake of an effect.
 */
export function useCountUp(target: number, active: boolean, durationMs = 1100): number {
  const reduced = usePrefersReducedMotion();
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!active) return;
    if (reduced) {
      setValue(target);
      return;
    }

    let frame = 0;
    let start: number | null = null;

    const step = (timestamp: number) => {
      start ??= timestamp;
      const progress = Math.min(1, (timestamp - start) / durationMs);
      // easeOutExpo
      const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      setValue(target * eased);
      if (progress < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, active, durationMs, reduced]);

  return value;
}

/** Inline style for a staggered entrance. */
export function stagger(index: number, stepMs = 70, baseMs = 0) {
  return { animationDelay: `${baseMs + index * stepMs}ms` };
}
