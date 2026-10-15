/** Regression coverage and test support for HoldIdFaceScan.test. */
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { HoldIdFaceScan } from './HoldIdFaceScan';

describe('ID beside face', () => {
  it('explains private human review and never presents a gallery file input', () => {
    const html = renderToStaticMarkup(createElement(HoldIdFaceScan, {
      value: null,
      onChange: () => undefined,
      disabled: true,
    }));
    expect(html).toContain('ID beside face');
    expect(html).toContain('manual review');
    expect(html).toContain('disabled');
    expect(html).not.toContain('type="file"');
  });
});
