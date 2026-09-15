import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const source = fs.readFileSync(path.join(process.cwd(), 'components/layout/DashboardLayout.tsx'), 'utf8');

describe('dashboard shell truthfulness and accessibility', () => {
    it('does not mount an empty local-only notification affordance', () => {
        expect(source).not.toContain("import { NotificationsBell }");
        expect(source).not.toContain('<NotificationsBell');
        expect(fs.existsSync(path.join(process.cwd(), 'components/layout/NotificationsBell.tsx'))).toBe(false);
    });

    it('names icon-only navigation and theme controls', () => {
        expect(source).toContain('aria-label="Open navigation menu"');
        expect(source).toContain("aria-label={theme === 'dark' ? 'Use light theme' : 'Use dark theme'}");
    });

    it('does not style the non-interactive profile avatar as clickable', () => {
        expect(source).not.toContain('cursor-pointer hover:ring-2');
    });
});
