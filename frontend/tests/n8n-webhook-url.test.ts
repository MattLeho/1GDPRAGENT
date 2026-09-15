import { describe, expect, it } from 'vitest';
import { validateN8nWebhookUrl, WebhookUrlValidationError } from '@/lib/security/webhook-url';

describe('N8N webhook URL validation', () => {
  it('accepts public and local HTTP(S) webhook endpoints', () => {
    expect(validateN8nWebhookUrl('https://automation.example.test/webhook/a')).toBe('https://automation.example.test/webhook/a');
    expect(validateN8nWebhookUrl('http://localhost:5678/webhook/a')).toBe('http://localhost:5678/webhook/a');
  });

  it.each([
    'ftp://automation.example.test/hook',
    'https://user:secret@automation.example.test/hook',
    'not-a-url',
    'https://automation.example.test/hook#secret',
  ])('rejects unsafe or unusable override %s', (value) => {
    expect(() => validateN8nWebhookUrl(value)).toThrow(WebhookUrlValidationError);
  });
});
