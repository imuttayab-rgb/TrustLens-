'use client';

import { uploadFile } from '@/lib/upload';
import { toApiError } from '@trustlens/api-client';
import { Alert, Spinner } from '@trustlens/ui';
import { Camera, Plus } from 'lucide-react';
import Image from 'next/image';
import { useRef, useState } from 'react';
import { useAddListingImage, useListingImages } from '../hooks/use-listings';

const MAX_IMAGES = 10;

export function ListingImages({ listingId }: { listingId: string }) {
  const { data: images = [], isPending } = useListingImages(listingId);
  const addImage = useAddListingImage(listingId);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    if (images.length + files.length > MAX_IMAGES) {
      setError(`A listing may have at most ${MAX_IMAGES} images.`);
      return;
    }

    setUploading(true);
    setError(null);
    setDuplicateWarning(null);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file) continue;
        if (images.length + i >= MAX_IMAGES) break;

        const fileId = await uploadFile('LISTING_IMAGE', file);
        const result = await addImage.mutateAsync(fileId);

        if (result.isDuplicate) {
          setDuplicateWarning(
            'One of your images appears to be a near-duplicate of an image you have already uploaded. Duplicate images do not improve your listing score.',
          );
        }
      }
    } catch (err) {
      setError(toApiError(err).message || 'Upload failed.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  if (isPending) {
    return <Spinner label="Loading images..." />;
  }

  return (
    <div className="space-y-4 rounded-lg border border-border p-4">
      <div>
        <h3 className="font-semibold">Photos</h3>
        <p className="text-sm text-muted-foreground">
          Upload up to {MAX_IMAGES} images. The first image will be the primary image. Good photos
          increase buyer trust.
        </p>
      </div>

      {error && (
        <Alert tone="error" title="Upload failed">
          {error}
        </Alert>
      )}
      {duplicateWarning && (
        <Alert tone="warning" title="Duplicate detected">
          {duplicateWarning}
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {images.map((img) => (
          <div
            key={img.imageId}
            className="group relative aspect-square overflow-hidden rounded-md border border-border bg-muted/50"
          >
            {img.thumbnailUrl || img.url ? (
              <Image
                src={img.thumbnailUrl ?? img.url ?? ''}
                alt="Listing image"
                fill
                className="object-cover"
                unoptimized // Presigned S3 URLs should not be cached/optimized by Next.js image proxy
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-muted-foreground">
                <Camera className="h-8 w-8 opacity-20" />
              </div>
            )}
            {img.isPrimary && (
              <div className="absolute left-2 top-2 rounded bg-background/80 px-1.5 py-0.5 text-[10px] font-medium uppercase shadow backdrop-blur">
                Primary
              </div>
            )}
          </div>
        ))}

        {images.length < MAX_IMAGES && (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex aspect-square cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-border text-muted-foreground transition-colors hover:border-foreground/50 hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
          >
            {uploading ? (
              <Spinner />
            ) : (
              <>
                <Plus className="h-6 w-6" />
                <span className="text-xs font-medium">Add Image</span>
              </>
            )}
          </button>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        className="hidden"
        onChange={(e) => void handleFileSelect(e)}
      />
    </div>
  );
}
