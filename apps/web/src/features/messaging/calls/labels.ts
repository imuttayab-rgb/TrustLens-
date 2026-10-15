/** Human-readable call outcomes; service reason codes remain stable. */
export const reasonLabel: Record<string, string> = {
  declined: 'Call declined',
  missed: 'No answer',
  cancelled: 'Call cancelled',
  ended: 'Call ended',
  failed: 'Could not connect. Please try again.',
  connection_lost: 'Connection lost. Please call again.',
  chat_unavailable: 'Calling is no longer available in this chat.',
  time_limit: 'Two-hour call limit reached.',
  unavailable: 'Calling is temporarily unavailable.',
};
export function errorText(error: unknown) {
  if (error instanceof Error && error.name === 'NotAllowedError')
    return 'Allow microphone access in your browser, then try again.';
  if (error instanceof Error && error.name === 'NotFoundError')
    return 'No microphone found. Connect a microphone and try again.';
  return error instanceof Error ? error.message : 'Could not complete the call. Please try again.';
}
