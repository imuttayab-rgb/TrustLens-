/** Reusable UI rendering and interaction component: ListingGallery. */
'use client';

import { cn } from '@trustlens/utils';
import { ChevronLeft, ChevronRight, Play, Video } from 'lucide-react';
import Image from 'next/image';
import { useState } from 'react';

interface GalleryImage {
  imageUrl: string;
  thumbnailUrl: string | null;
  isPrimary: boolean;
}

type Slide = { kind: 'video'; url: string } | { kind: 'image'; image: GalleryImage };

/**
 * The media carousel on a listing page: main slide, prev/next arrows, a
 * counter, and a thumbnail strip.
 *
 * Post-an-Ad v2: when the seller attached a product video it is the FIRST
 * slide (a buyer sees the real item before the photos), with a play
 * thumbnail in the strip and a "Seller video" label. It never autoplays and
 * starts muted; recorded clips carry no audio because the recorder never
 * asks for the microphone.
 */
export function ListingGallery({
  images,
  title,
  videoUrl = null,
}: {
  images: GalleryImage[];
  title: string;
  videoUrl?: string | null;
}) {
  const slides: Slide[] = [
    ...(videoUrl ? [{ kind: 'video' as const, url: videoUrl }] : []),
    ...images.map((image) => ({ kind: 'image' as const, image })),
  ];
  const [index, setIndex] = useState(0);

  if (slides.length === 0) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-dashed border-border bg-muted/50 text-sm text-muted-foreground">
        No photos
      </div>
    );
  }

  const safeIndex = Math.min(index, slides.length - 1);
  const active = slides[safeIndex]!;
  const videoOffset = videoUrl ? 1 : 0;

  function go(delta: number) {
    setIndex((i) => (i + delta + slides.length) % slides.length);
  }

  return (
    <div className="space-y-2">
      <div className="group relative aspect-[4/3] overflow-hidden rounded-xl border border-border bg-black">
        {active.kind === 'video' ? (
          <video
            key={active.url}
            src={active.url}
            controls
            muted
            playsInline
            preload="metadata"
            className="h-full w-full object-contain"
            aria-label={`${title} - seller video`}
          />
        ) : (
          <Image
            key={active.image.imageUrl}
            src={active.image.imageUrl}
            alt={`${title} - photo ${safeIndex + 1 - videoOffset}`}
            fill
            className="animate-fade-in bg-muted object-cover"
            unoptimized
            priority
          />
        )}

        {active.kind === 'video' && (
          <span className="pointer-events-none absolute left-3 top-3 inline-flex items-center gap-1 rounded-full bg-brand px-2.5 py-1 text-xs font-semibold text-white shadow">
            <Video className="h-3.5 w-3.5" aria-hidden="true" />
            Seller video
          </span>
        )}

        {slides.length > 1 && (
          <>
            <span className="absolute right-3 top-3 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white">
              {active.kind === 'video'
                ? `Video · ${images.length} photos`
                : `${safeIndex + 1 - videoOffset} / ${images.length} photos`}
            </span>
            <button
              type="button"
              aria-label="Previous"
              onClick={() => go(-1)}
              className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-foreground opacity-0 shadow-md transition-opacity duration-150 hover:bg-white focus-visible:opacity-100 group-hover:opacity-100"
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="Next"
              onClick={() => go(1)}
              className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-foreground opacity-0 shadow-md transition-opacity duration-150 hover:bg-white focus-visible:opacity-100 group-hover:opacity-100"
            >
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </>
        )}
      </div>

      {slides.length > 1 && (
        <div className="grid grid-cols-4 gap-2 sm:grid-cols-5">
          {slides.map((slide, i) => (
            <button
              key={slide.kind === 'video' ? 'seller-video' : slide.image.imageUrl}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={
                slide.kind === 'video' ? 'Play seller video' : `View photo ${i + 1 - videoOffset}`
              }
              aria-current={i === safeIndex}
              className={cn(
                'relative aspect-square overflow-hidden rounded-md border-2 bg-muted transition-colors',
                i === safeIndex ? 'border-brand' : 'border-transparent hover:border-border',
              )}
            >
              {slide.kind === 'video' ? (
                <span className="flex h-full w-full flex-col items-center justify-center gap-1 bg-slate-900 text-white">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-slate-900">
                    <Play className="ml-0.5 h-4 w-4" aria-hidden="true" />
                  </span>
                  <span className="text-[10px] font-semibold uppercase tracking-wide">Video</span>
                </span>
              ) : (
                <Image
                  src={slide.image.thumbnailUrl ?? slide.image.imageUrl}
                  alt={`${title} thumbnail ${i + 1 - videoOffset}`}
                  fill
                  className="object-cover"
                  unoptimized
                />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
