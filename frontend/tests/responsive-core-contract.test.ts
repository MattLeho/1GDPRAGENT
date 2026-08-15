import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = (path: string) => readFileSync(resolve(process.cwd(), path), 'utf8');

describe('responsive core workflow contract', () => {
  it('keeps the compact shell until the main panel can support a desktop sidebar', () => {
    const layout = source('components/layout/DashboardLayout.tsx');
    expect(layout).toContain('lg:hidden');
    expect(layout).toContain('lg:flex');
    expect(layout).toContain('min-w-0 flex-1');
  });

  it('reflows request actions and filters instead of clipping fixed rows', () => {
    const page = source('app/dashboard/requests/page.tsx');
    const toolbar = source('components/requests/SearchToolbar.tsx');
    expect(page).toContain('flex flex-col gap-4 xl:flex-row');
    expect(page).toContain('sm:grid-cols-3');
    expect(page).toContain('href="/dashboard/onsit"');
    expect(toolbar).toContain('sm:grid-cols-2 xl:grid-cols-');
    expect(toolbar).toContain('placeholder="Search companies or brokers..."');
    expect(toolbar).not.toContain('w-[130px]');
  });

  it('does not subtract a desktop sidebar from request overlays on compact screens', () => {
    const modal = source('components/requests/RequestDetailModal.tsx');
    const sheet = source('components/requests/RequestDetailSheet.tsx');
    expect(modal).toContain('w-[calc(100vw-1rem)]');
    expect(modal).toContain('lg:w-[calc(100vw-16rem)]');
    expect(sheet).toContain('max-w-full');
    expect(sheet).not.toContain('max-w-[calc(100vw-200px)]');
  });
});

