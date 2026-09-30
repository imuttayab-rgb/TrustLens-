'use client';

import { cn } from '@trustlens/utils';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import Image from 'next/image';
import { useState } from 'react';

interface GalleryImage {
  imageUrl: string;
  thumbnailUrl: string | null;
  isPrimary: boolean;
}

/** The photo carousel on a listing page - main image, prev/next arrows, a
 * "n / total" counter, and a thumbnail strip to jump directly to a photo. */
export function ListingGallery({ images, title }: { images: GalleryImage[]; title: string }) {
  const [index, setIndex] = useState(0);

  if (images.length === 0) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-dashed border-border bg-muted/50 text-sm text-muted-foreground">
        No photos
      </div>
    );
  }

  const active = images[index]!;

  function go(delta: number) {
    setIndex((i) => (i + delta + images.length) % images.length);
  }

  return (
    <div className="space-y-2">
      <div className="group relative aspect-[4/3] overflow-hidden rounded-xl border border-border bg-muted">
        <Image
          key={active.imageUrl}
          src={active.imageUrl}
          alt={`${title} - photo ${index + 1}`}
          fill
          className="animate-fade-in object-cover"
          unoptimized
          priority
        />

        {images.length > 1 && (
          <>
            <span className="absolute right-3 top-3 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white">
              {index + 1} / {images.length} photos
            </span>
            <button
              type="button"
              aria-label="Previous photo"
              onClick={() => go(-1)}
              className="absolute left-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-foreground opacity-0 shadow-md transition-opacity duration-150 hover:bg-white group-hover:opacity-100"
            >
              <ChevronLeft className="h-5 w-5" aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-label="Next photo"
              onClick={() => go(1)}
              className="absolute right-3 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-full bg-white/90 text-foreground opacity-0 shadow-md transition-opacity duration-150 hover:bg-white group-hover:opacity-100"
            >
              <ChevronRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </>
        )}
      </div>

      {images.length > 1 && (
        <div className="grid grid-cols-4 gap-2">
          {images.map((image, i) => (
            <button
              key={image.imageUrl}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`View photo ${i + 1}`}
              aria-current={i === index}
              className={cn(
                'relative aspect-square overflow-hidden rounded-md border-2 bg-muted transition-colors',
                i === index ? 'border-brand' : 'border-transparent hover:border-border',
              )}
            >
              <Image
                src={image.thumbnailUrl ?? image.imageUrl}
                alt={`${title} thumbnail ${i + 1}`}
                fill
                className="object-cover"
                unoptimized
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
