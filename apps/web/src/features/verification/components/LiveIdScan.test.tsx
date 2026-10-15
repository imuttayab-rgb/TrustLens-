/** Regression coverage and test support for LiveIdScan.test. */
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { LiveIdScan } from './LiveIdScan';

describe('live-only card capture presentation', () => {
  it('has no file/gallery input and keeps the camera disabled before consent', () => {
    const markup = renderToStaticMarkup(createElement(LiveIdScan, {
      side: 'front',
      value: null,
      onChange: vi.fn(),
      disabled: true,
    }));
    expect(markup).not.toContain('type="file"');
    expect(markup).toContain('Start live front scan');
    expect(markup).toContain('disabled');
  });

  it('prompts separately for the back without exposing an image picker', () => {
    const markup = renderToStaticMarkup(createElement(LiveIdScan, {
      side: 'back',
      value: null,
      onChange: vi.fn(),
      disabled: false,
    }));
    expect(markup).toContain('Start live back scan');
    expect(markup).not.toContain('type="file"');
  });
});
