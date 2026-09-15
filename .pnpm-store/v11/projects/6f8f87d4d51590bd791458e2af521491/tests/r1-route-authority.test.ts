import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'fs';
import { join, relative, resolve, sep } from 'path';
import ts from 'typescript';

const apiRoot = resolve(process.cwd(), 'app/api');
const expected: Record<string, string[]> = {
  'auth/check-setup': ['GET'], 'auth/login': ['POST'], 'auth/logout': ['POST'],
  'auth/register': ['POST'], 'auth/session': ['GET'],
  'connectors/[[...path]]': ['DELETE', 'GET', 'POST', 'PUT'], 'execution': ['POST'],
  'gdpr-agent/analyze-policy': ['POST'], 'gdpr-agent/draft': ['POST'], 'graph': ['GET'],
  'graph/chat': ['POST'], 'graph/nodes': ['DELETE', 'POST', 'PUT'], 'graph/nodes/bulk': ['POST'],
  'graph/nodes/merge': ['POST'], 'graph/stats': ['GET'], 'graph/upsert-identity': ['POST'],
  'identities': ['GET'], 'identities/account': ['POST'], 'ingestion/benchmark-invoke': ['POST'],
  'ingestion/feature-adjudication': ['POST'], 'ingestion/schema-interpretation': ['POST'],
  'insights/[module]': ['GET'], 'insights/context-events': ['POST'], 'insights/evidence/[id]': ['GET'],
  'insights/media-analysis': ['GET', 'POST'], 'insights/media-location-confirmations': ['POST'],
  'n8n/analyze-policy': ['POST'], 'n8n/test-imap': ['POST'], 'onsit/bulk': ['POST'],
  'onsit/discover': ['POST'], 'onsit/discover-dpo': ['POST'], 'onsit/export': ['GET'],
  'onsit/extract-vendors': ['POST'], 'onsit/findings/[id]': ['DELETE', 'GET'],
  'onsit/send-bulk-emails': ['POST'], 'onsit/status/[taskId]': ['GET'],
  'onsit/vendor-bulk-email': ['POST'], 'onsit/vendor-domain-search': ['POST'],
  'onsit/vendor-dpo-discovery': ['POST'], 'policy/check': ['POST'],
  'request-threads': ['GET', 'POST'], 'request-threads/[id]/chat': ['GET', 'POST'],
  'requests/[id]': ['DELETE'], 'requests/[id]/logs': ['GET'],
  'retention/[[...path]]': ['GET', 'POST'], 'settings/ai-credentials': ['GET', 'POST'],
  'settings/ai-models': ['GET'], 'settings/api-credentials': ['GET', 'POST'],
  'settings/engine-health/[engineId]': ['GET'], 'settings/execution-audit': ['GET'],
  'settings/id-documents': ['DELETE', 'GET', 'POST'], 'settings/model-preferences': ['GET', 'POST'],
  'settings/n8n-webhooks': ['GET', 'POST'], 'settings/processing': ['GET', 'POST'],
  'settings/profile': ['GET', 'POST', 'PUT'], 'settings/profile/password': ['POST'],
  'settings/task-routes': ['GET', 'POST'], 'settings/workflows': ['GET', 'POST'],
  'upload': ['DELETE', 'GET', 'PATCH', 'POST'], 'upload/process': ['POST', 'PUT'],
  'upload/scan': ['POST'], 'workflows/inbox-monitor': ['POST'],
};

const publicRoutes = new Set(['auth/check-setup', 'auth/login', 'auth/logout', 'auth/register']);

function walk(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : entry.name === 'route.ts' ? [path] : [];
  });
}

function routeName(path: string): string {
  return relative(apiRoot, join(path, '..')).split(sep).join('/');
}

function methods(source: string): string[] {
  const file = ts.createSourceFile('route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const result = new Set<string>();
  for (const statement of file.statements) {
    const modifiers = ts.canHaveModifiers(statement) ? ts.getModifiers(statement) : undefined;
    const exported = modifiers?.some(modifier => modifier.kind === ts.SyntaxKind.ExportKeyword);
    if (exported && (ts.isFunctionDeclaration(statement) || ts.isVariableStatement(statement))) {
      if (ts.isFunctionDeclaration(statement) && statement.name && /^(GET|POST|PUT|PATCH|DELETE)$/.test(statement.name.text)) result.add(statement.name.text);
      if (ts.isVariableStatement(statement)) for (const declaration of statement.declarationList.declarations) {
        if (ts.isIdentifier(declaration.name) && /^(GET|POST|PUT|PATCH|DELETE)$/.test(declaration.name.text)) result.add(declaration.name.text);
      }
    }
    if (ts.isExportDeclaration(statement) && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
      for (const element of statement.exportClause.elements) if (/^(GET|POST|PUT|PATCH|DELETE)$/.test(element.name.text)) result.add(element.name.text);
    }
  }
  return [...result].sort();
}

function exportedMethodBodies(source: string): Map<string, string> {
  const file = ts.createSourceFile('route.ts', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const result = new Map<string, string>();
  const namedBodies = new Map<string, string>();
  for (const statement of file.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name && statement.body) {
      const name = statement.name.text;
      namedBodies.set(name, statement.body.getText(file));
      if (['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(name)) result.set(name, statement.body.getText(file));
    }
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!ts.isIdentifier(declaration.name) || !declaration.initializer) continue;
        const name = declaration.name.text;
        if (!['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].includes(name)) continue;
        if (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer)) {
          result.set(name, declaration.initializer.body.getText(file));
        } else if (ts.isIdentifier(declaration.initializer)) {
          const body = namedBodies.get(declaration.initializer.text);
          if (body) result.set(name, body);
        }
      }
    }
    if (ts.isExportDeclaration(statement) && statement.exportClause && ts.isNamedExports(statement.exportClause)) {
      for (const element of statement.exportClause.elements) {
        if (!/^(GET|POST|PUT|PATCH|DELETE)$/.test(element.name.text)) continue;
        const localName = element.propertyName?.text || element.name.text;
        const body = namedBodies.get(localName);
        if (body) result.set(element.name.text, body);
      }
    }
  }
  return result;
}

describe('R1 route authority inventory', () => {
  const files = new Map(walk(apiRoot).map(path => [routeName(path), path]));

  it('fails on an unclassified route or method', () => {
    expect([...files.keys()].sort()).toEqual(Object.keys(expected).sort());
    for (const [route, path] of files) {
      expect(methods(readFileSync(path, 'utf8')), route).toEqual(expected[route].slice().sort());
    }
  });

  it('requires each sensitive method to await, return, and order the canonical guard first', () => {
    for (const [route, path] of files) {
      if (publicRoutes.has(route)) continue;
      const bodies = exportedMethodBodies(readFileSync(path, 'utf8'));
      for (const method of expected[route]) {
        const body = bodies.get(method);
        expect(body, `${route} ${method}`).toBeDefined();
        const guardIndex = body!.indexOf('await requireApiSession(');
        expect(guardIndex, `${route} ${method} must await the guard`).toBeGreaterThanOrEqual(0);
        expect(body, `${route} ${method} must return a rejected authority response`).toMatch(
          /if\s*\(\s*authority\s+instanceof\s+NextResponse\s*\)\s*return\s+authority/,
        );
        const protectedWork = [body!.indexOf('request.json('), body!.indexOf('pool.query('), body!.indexOf('fetch(')]
          .filter(index => index >= 0);
        if (protectedWork.length > 0) {
          expect(guardIndex, `${route} ${method} guard must precede parsing, database, and network work`)
            .toBeLessThan(Math.min(...protectedWork));
        }
      }
    }
  });

  it('derives the Personal Insights subject from authority', () => {
    const source = readFileSync(files.get('insights/[module]')!, 'utf8');
    expect(source).toContain("query.set('subject_id', authority.profileId)");
    expect(source).not.toMatch(/SELECT\s+id\s+FROM\s+user_profiles.*LIMIT\s+1/i);
  });
});
