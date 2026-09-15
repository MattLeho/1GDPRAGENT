import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'fs';
import { join, relative, resolve, sep } from 'path';
import ts from 'typescript';

const callPattern = /intelligenceAuthorityHeaders\s*\(/g;
const intelligenceTargetPattern = /INTELLIGENCE_(?:SERVICE_)?URL|intelligence:8000|localhost:800[01]/;

function walk(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory() && !['node_modules', '.next'].includes(entry.name)) return walk(path);
    return entry.isFile() && /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

function intelligenceFetchCount(source: string): number {
  const file = ts.createSourceFile('candidate.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const tainted = new Set<string>();
  const networkCallers = new Set(['fetch', 'axios', 'got', 'request']);
  const declarations: Array<{ name: string; text: string }> = [];
  const collect = (node: ts.Node) => {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const initializer = node.initializer.getText(file);
      declarations.push({ name: node.name.text, text: initializer });
      if (/^(fetch|axios|got|request)$/.test(initializer)) networkCallers.add(node.name.text);
    }
    if (ts.isFunctionDeclaration(node) && node.name && node.body) declarations.push({ name: node.name.text, text: node.body.getText(file) });
    ts.forEachChild(node, collect);
  };
  collect(file);
  let changed = true;
  while (changed) {
    changed = false;
    for (const declaration of declarations) {
      if (tainted.has(declaration.name)) continue;
      if (intelligenceTargetPattern.test(declaration.text) || [...tainted].some(name => new RegExp(`\\b${name}\\b`).test(declaration.text))) {
        tainted.add(declaration.name); changed = true;
      }
    }
  }
  let count = 0;
  const inspect = (node: ts.Node) => {
    if (ts.isCallExpression(node) && node.arguments[0]) {
      const callee = node.expression.getText(file);
      const isNetwork = networkCallers.has(callee) || /\.(?:request|fetch)$/.test(callee);
      const argument = node.arguments[0].getText(file);
      if (isNetwork && (intelligenceTargetPattern.test(argument) || [...tainted].some(name => new RegExp(`\\b${name}\\b`).test(argument)))) count++;
    }
    ts.forEachChild(node, inspect);
  };
  inspect(file);
  return count;
}

describe('R1 signed Next-to-Intelligence call sites', () => {
  it('signs every inventoried Intelligence fetch separately', () => {
    const candidates = [resolve(process.cwd(), 'app'), resolve(process.cwd(), 'lib')].flatMap(walk).filter(path => {
      const source = readFileSync(path, 'utf8');
      return /(?:fetch|axios|got|request)\s*\(|\.(?:request|fetch)\s*\(/.test(source) && intelligenceTargetPattern.test(source);
    });
    expect(candidates.length).toBeGreaterThan(0);
    for (const path of candidates) {
      const source = readFileSync(path, 'utf8');
      const label = relative(process.cwd(), path).split(sep).join('/');
      const fetches = intelligenceFetchCount(source);
      const signedHeaders = [...source.matchAll(callPattern)].length;
      expect(fetches, `${label} must expose at least one Intelligence fetch to discovery`).toBeGreaterThan(0);
      expect(signedHeaders, `${label} must sign every discovered Intelligence fetch`).toBe(fetches);
    }
  });

  it('passes canonical profile authority through execution and ingestion helpers', () => {
    const router = readFileSync(resolve(process.cwd(), 'lib/execution/router.ts'), 'utf8');
    const bulk = readFileSync(resolve(process.cwd(), 'lib/ingestion/bulk.ts'), 'utf8');
    const graph = readFileSync(resolve(process.cwd(), 'lib/graph/upsert.ts'), 'utf8');
    expect(router).toContain('invocation.profileId');
    expect(router).toContain("intelligenceAuthorityHeaders(profileId,target,'POST','application/json',undefined,undefined,body)");
    expect(bulk).toContain("intelligenceAuthorityHeaders(profileId,processTarget,'POST','application/json',undefined,undefined,processBody)");
    expect(bulk).toContain("intelligenceAuthorityHeaders(profileId,resultTarget,'POST','application/json',undefined,undefined,reportBody)");
    expect(graph).toContain("intelligenceAuthorityHeaders(profileId,target,'POST','application/json',undefined,undefined,body)");
  });
});
