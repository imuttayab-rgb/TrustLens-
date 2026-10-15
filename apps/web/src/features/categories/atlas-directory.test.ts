import { describe, expect, it } from 'vitest';
import {
  MARKETPLACE_NODES,
  MARKETPLACE_ROOTS,
  categoryBrowseHref,
  withBrowseLocation,
} from '@trustlens/constants';
import {
  ATLAS_GROUPS,
  ATLAS_PREVIEW_LIMITS,
  atlasChildren,
  atlasPreview,
  searchAtlas,
} from './atlas-directory';

describe('Night Atlas category navigation contract', () => {
  it('uses bounded previews without removing hidden entries', () => {
    for (const root of MARKETPLACE_ROOTS) {
      const preview = atlasPreview(root.id);
      const complete = atlasChildren(root.id);
      expect(preview).toHaveLength(Math.min(ATLAS_PREVIEW_LIMITS[root.id] ?? 5, complete.length));
      expect(new Set(preview.map((n) => n.id)).size).toBe(preview.length);
      expect(preview.every((n) => n.parentId === root.id)).toBe(true);
      for (const node of complete.filter((n) => !preview.some((p) => p.id === n.id))) {
        expect(searchAtlas(node.label).some((n) => n.node.id === node.id)).toBe(true);
      }
    }
    expect(atlasPreview('animals')).toHaveLength(3);
    expect(atlasChildren('animals').length).toBeGreaterThan(5);
  });
  it('separates Property from Transport while keeping every vehicle and bike type visible', () => {
    expect(ATLAS_GROUPS.map((g) => g.id)).toEqual([
      'technology',
      'transport',
      'property',
      'living',
      'work',
    ]);
    expect(ATLAS_GROUPS.find((g) => g.id === 'transport')?.categories.map((n) => n.id)).toEqual([
      'vehicles',
      'bikes',
    ]);
    expect(ATLAS_GROUPS.find((g) => g.id === 'property')?.categories.map((n) => n.id)).toEqual([
      'property-sale',
      'property-rent',
    ]);
    for (const root of ['vehicles', 'bikes', 'property-sale', 'property-rent']) {
      expect(
        atlasPreview(root)
          .map((n) => n.id)
          .sort(),
      ).toEqual(
        atlasChildren(root)
          .map((n) => n.id)
          .sort(),
      );
    }
    for (const slug of [
      'cars',
      'buses-vans-trucks',
      'tractors-trailers',
      'rickshaw-chingchi',
      'boats',
      'spare-parts',
    ]) {
      expect(atlasPreview('vehicles').some((n) => n.id === 'vehicles/' + slug)).toBe(true);
    }
    expect(
      ATLAS_GROUPS.flatMap((g) => g.categories.flatMap((n) => atlasPreview(n.id))),
    ).toHaveLength(74);
  });
  it('keeps cosmetics and skincare visible in the compact fashion shortcuts', () => {
    const ids = atlasPreview('fashion-beauty').map((n) => n.id);
    expect(ids).toContain('fashion-beauty/cosmetics');
    expect(ids).toContain('fashion-beauty/skincare');
    expect(atlasPreview('not-a-category')).toEqual([]);
  });
  it('keeps every existing root once, without dropping service or non-physical categories', () => {
    const roots = ATLAS_GROUPS.flatMap((g) => g.categories.map((n) => n.id));
    expect(new Set(roots).size).toBe(roots.length);
    expect([...roots].sort()).toEqual(MARKETPLACE_ROOTS.map((n) => n.id).sort());
  });
  it('makes every catalogue level reachable from the visible root groups', () => {
    const visited = new Set<string>();
    const visit = (id: string) => {
      expect(visited.has(id)).toBe(false);
      visited.add(id);
      atlasChildren(id).forEach((n) => visit(n.id));
    };
    ATLAS_GROUPS.forEach((g) => g.categories.forEach((n) => visit(n.id)));
    expect([...visited].sort()).toEqual(MARKETPLACE_NODES.map((n) => n.id).sort());
  });
  it('generates exact internal browse destinations for all nodes and carries only public location', () => {
    const current = new URLSearchParams(
      'city=Lahore&area=Johar+Town&lat=31.5&lng=74.3&radius=10&q=old&token=private&categoryNodeId=old',
    );
    for (const node of MARKETPLACE_NODES) {
      const url = new URL(
        withBrowseLocation(categoryBrowseHref(node.id), current),
        'https://trustlens.test',
      );
      expect(url.origin).toBe('https://trustlens.test');
      expect(url.pathname).toBe('/browse');
      expect(url.searchParams.get('categoryNodeId')).toBe(node.id);
      expect(url.searchParams.get('city')).toBe('Lahore');
      expect(url.searchParams.get('area')).toBe('Johar Town');
      expect(url.searchParams.has('token')).toBe(false);
      expect(url.searchParams.has('q')).toBe(false);
      expect(url.hash).toBe('');
    }
  });
  it('searches English and Urdu labels including roots and deep branches', () => {
    for (const node of MARKETPLACE_NODES) {
      expect(searchAtlas(node.label).some((row) => row.node.id === node.id)).toBe(true);
      expect(searchAtlas(node.labelUr).some((row) => row.node.id === node.id)).toBe(true);
    }
    expect(
      searchAtlas('  MOBILE   PHONES ').some((r) => r.node.id === 'mobiles/mobile-phones'),
    ).toBe(true);
    expect(searchAtlas('cosmetics').length).toBeGreaterThan(0);
    expect(searchAtlas('skincare').length).toBeGreaterThan(0);
    expect(searchAtlas('zzzz-no-category-zzzz')).toEqual([]);
    expect(searchAtlas('   ')).toEqual([]);
  });
});
