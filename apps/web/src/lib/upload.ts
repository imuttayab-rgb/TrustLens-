'use client';

import { api } from '@/lib/api/client';
import { toApiError } from '@trustlens/api-client';

/**
 * Direct-to-storage upload.
 *
 * The API never receives the bytes: it issues a presigned POST and the browser
 * sends the file straight to object storage. That keeps a 10 MB photo off the
 * request path entirely.
 */

export interface UploadIntent {
  fileId: string;
  uploadUrl: string;
  fields: Record<string, string>;
  expiresAt: string;
  maxBytes: number;
}

/**
 * Longest edge kept when re-encoding, in pixels.
 *
 * This is an accuracy decision, not a bandwidth one. OCR accuracy on a CNIC
 * falls off sharply once the text stops being crisply resolved, and the
 * 13-digit number is the smallest thing on the card. 2000px keeps a
 * full-frame CNIC comfortably readable while cutting a modern phone photo
 * (4000px+, 6-10 MB) to roughly a tenth of the size - which matters a great
 * deal on a Pakistani mobile connection.
 *
 * Do not lower this to "make uploads faster" without re-running
 * `apps/ml/bench/ocr_bench.py`. It will trade accuracy you cannot see for
 * seconds you can.
 */
const MAX_EDGE_PX = 2000;
const JPEG_QUALITY = 0.9;

/** Re-encode oversized photos; leave small or non-photo files alone. */
export async function compressImage(file: File): Promise<File> {
  if (!file.type.startsWith('image/') || file.type === 'image/webp') return file;

  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    // A file the browser cannot decode is the server's problem to reject,
    // not something to fail the upload over here.
    return file;
  }

  const longest = Math.max(bitmap.width, bitmap.height);
  if (longest <= MAX_EDGE_PX) {
    bitmap.close();
    return file;
  }

  const scale = MAX_EDGE_PX / longest;
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);

  const context = canvas.getContext('2d');
  if (!context) {
    bitmap.close();
    return file;
  }
  context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY),
  );
  if (!blob || blob.size >= file.size) return file;

  return new File([blob], file.name.replace(/\.\w+$/, '') + '.jpg', {
    type: 'image/jpeg',
    lastModified: file.lastModified,
  });
}

async function requestIntent(purpose: string, file: File): Promise<UploadIntent> {
  const result = await api.POST('/api/v1/files/upload-intent', {
    body: {
      purpose,
      contentType: file.type,
      sizeBytes: file.size,
      filename: file.name,
    },
  });
  if (result.error) throw toApiError(result.error);
  return (result.data as { data: UploadIntent }).data;
}

/**
 * POST the file to storage using the presigned form.
 *
 * Field order matters: S3 and MinIO require every policy field to precede the
 * file part, and silently reject the request otherwise.
 */
async function putToStorage(intent: UploadIntent, file: File, signal?: AbortSignal) {
  const form = new FormData();
  for (const [key, value] of Object.entries(intent.fields)) form.append(key, value);
  form.append('file', file);

  const response = await fetch(intent.uploadUrl, {
    method: 'POST',
    body: form,
    // A presigned POST authenticates itself; sending cookies to the storage
    // origin would be both useless and a cross-origin leak.
    credentials: 'omit',
    ...(signal ? { signal } : {}),
  });

  if (!response.ok) {
    throw new Error(`Storage rejected the upload (${response.status}).`);
  }
}

export interface UploadOptions {
  /** 0-100, reported as the upload progresses through its stages. */
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
  /** Network attempts before giving up. */
  retries?: number;
}

/**
 * Compress, request an intent, upload, and return the file id.
 *
 * Retries only the storage PUT, and only on network-shaped failures. A mobile
 * connection drops mid-upload often enough that a single attempt makes the
 * verification flow feel broken; a rejected presigned policy, by contrast,
 * will fail identically every time and must not be retried.
 */
export async function uploadFile(
  purpose: string,
  file: File,
  { onProgress, signal, retries = 2 }: UploadOptions = {},
): Promise<string> {
  onProgress?.(5);
  const prepared = await compressImage(file);
  onProgress?.(25);

  const intent = await requestIntent(purpose, prepared);
  onProgress?.(40);

  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      await putToStorage(intent, prepared, signal);
      onProgress?.(100);
      return intent.fileId;
    } catch (error) {
      if (signal?.aborted) throw error;
      lastError = error;
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** attempt));
        onProgress?.(40 + attempt * 10);
      }
    }
  }
  throw lastError instanceof Error ? lastError : new Error('Upload failed.');
}
