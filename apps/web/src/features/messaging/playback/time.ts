/** Human-readable recording/playback elapsed time. */
export const voiceTime = (value: number) =>
  `${Math.floor(value / 60)}:${Math.floor(value % 60)
    .toString()
    .padStart(2, '0')}`;
