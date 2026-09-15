export class WebhookUrlValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'WebhookUrlValidationError';
  }
}

/**
 * Validate an operator-supplied N8N endpoint. Local/private hosts are allowed
 * because N8N commonly runs inside the trusted Compose network; credentials
 * and fragments are not useful webhook routing data and must not be stored.
 */
export function validateN8nWebhookUrl(rawUrl: string): string {
  if (rawUrl.length > 2048) {
    throw new WebhookUrlValidationError('Webhook URL is too long');
  }

  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new WebhookUrlValidationError('Webhook URL must be an absolute URL');
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new WebhookUrlValidationError('Webhook URL must use HTTP or HTTPS');
  }
  if (url.username || url.password) {
    throw new WebhookUrlValidationError('Webhook URL must not contain credentials');
  }
  if (url.hash) {
    throw new WebhookUrlValidationError('Webhook URL must not contain a fragment');
  }

  return url.toString();
}
