const REQUIRED_PRODUCTION_SECRETS = [
  'SESSION_SIGNING_KEY',
  'INTERNAL_API_KEY',
  'CREDENTIALS_ENCRYPTION_KEY',
] as const;

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === 'nodejs' && process.env.NODE_ENV === 'production') {
    const missing = REQUIRED_PRODUCTION_SECRETS.filter(name => !process.env[name]);
    if (missing.length > 0) {
      throw new Error(`Missing required production secrets: ${missing.join(', ')}`);
    }
  }
}
