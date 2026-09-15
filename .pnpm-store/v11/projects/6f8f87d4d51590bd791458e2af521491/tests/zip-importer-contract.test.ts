import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const source = readFileSync(
  resolve(process.cwd(), 'components/dashboard/ZipImporter.tsx'),
  'utf8',
);
const importPage = readFileSync(
  resolve(process.cwd(), 'app/dashboard/import/page.tsx'),
  'utf8',
);

describe('ZIP importer evidence contract', () => {
  it('records each successfully processed file without claiming graph projection', () => {
    expect(source).not.toContain("method: 'PUT'");
    expect(source).not.toContain('Knowledge graph updated');
    expect(source).not.toContain('added to knowledge graph');
    expect(source).not.toContain('markdownContent: result.content');

    expect(source).toContain('Evidence recorded');
    expect(source).toContain('awaiting review before graph projection');
    expect(source).toContain('onComplete?.(processedFiles.filter');
  });

  it('does not expose the simulated broker scanner as an operational tool', () => {
    expect(importPage).not.toContain('DatabrokerScanner');
    expect(importPage).toContain('/dashboard/onsit');
    expect(importPage).toContain('Open broker discovery');
  });
});
