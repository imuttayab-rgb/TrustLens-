/** Profileavatar module; defines ProfileAvatar. */
'use client';
import Image from 'next/image';
import { useState } from 'react';
import { photoUrl } from './api';
export function ProfileAvatar({
  src,
  name,
  size = 64,
}: {
  src?: string | null | undefined;
  name: string;
  size?: number;
}) {
  const [failed, setFailed] = useState<string | null>(null);
  const url = photoUrl(src);
  return (
    <span
      className="relative grid shrink-0 place-items-center overflow-hidden rounded-full border-2 border-brand/60 bg-brand/10 font-bold text-brand"
      style={{ width: size, height: size, fontSize: size * 0.3 }}
    >
      {url && failed !== url ? (
        <Image
          src={url}
          alt={`${name}'s profile photo`}
          fill
          sizes={`${size}px`}
          unoptimized
          className="object-cover"
          onError={() => setFailed(url)}
        />
      ) : (
        name.slice(0, 1).toUpperCase()
      )}
    </span>
  );
}
