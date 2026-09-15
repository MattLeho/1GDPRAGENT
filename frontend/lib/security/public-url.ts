import { lookup } from 'node:dns/promises';
import { isIP } from 'node:net';

export interface ResolvedHostAddress {
  address: string;
  family: number;
}

export type HostResolver = (hostname: string) => Promise<ResolvedHostAddress[]>;

export class PublicUrlValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PublicUrlValidationError';
  }
}

const defaultResolver: HostResolver = (hostname) => lookup(hostname, {
  all: true,
  verbatim: true,
});

function isPublicIpv4(address: string): boolean {
  const octets = address.split('.').map(Number);
  if (octets.length !== 4 || octets.some(value => !Number.isInteger(value) || value < 0 || value > 255)) {
    return false;
  }
  const [a, b, c] = octets;
  if (a === 0 || a === 10 || a === 127 || a >= 224) return false;
  if (a === 100 && b >= 64 && b <= 127) return false;
  if (a === 169 && b === 254) return false;
  if (a === 172 && b >= 16 && b <= 31) return false;
  if (a === 192 && (b === 168 || (b === 0 && (c === 0 || c === 2)))) return false;
  if (a === 198 && (b === 18 || b === 19 || (b === 51 && c === 100))) return false;
  if (a === 203 && b === 0 && c === 113) return false;
  return true;
}

function isPublicIp(address: string): boolean {
  const normalized = address.toLowerCase().replace(/^\[|\]$/g, '');
  const family = isIP(normalized);
  if (family === 4) return isPublicIpv4(normalized);
  if (family !== 6) return false;

  if (normalized === '::' || normalized === '::1') return false;
  if (/^(fc|fd)/.test(normalized) || /^fe[89ab]/.test(normalized) || normalized.startsWith('ff')) return false;
  if (normalized.startsWith('2001:db8:')) return false;
  if (normalized.startsWith('::ffff:')) return isPublicIpv4(normalized.slice(7));
  return true;
}

export async function assertPublicHttpUrl(
  rawUrl: string,
  resolveHost: HostResolver = defaultResolver,
): Promise<URL> {
  let url: URL;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new PublicUrlValidationError('Policy URL must be a valid absolute URL');
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new PublicUrlValidationError('Policy URL must use HTTP or HTTPS');
  }
  if (url.username || url.password) {
    throw new PublicUrlValidationError('Policy URL must not contain credentials');
  }

  const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, '');
  if (!hostname || hostname === 'localhost' || hostname.endsWith('.localhost') ||
      hostname.endsWith('.local') || hostname.endsWith('.internal')) {
    throw new PublicUrlValidationError('Policy URL must use a public hostname');
  }

  const literalFamily = isIP(hostname);
  if (!literalFamily && !hostname.includes('.')) {
    throw new PublicUrlValidationError('Policy URL must use a public hostname');
  }

  let addresses: ResolvedHostAddress[];
  try {
    addresses = literalFamily
      ? [{ address: hostname, family: literalFamily }]
      : await resolveHost(hostname);
  } catch {
    throw new PublicUrlValidationError('Policy URL hostname could not be resolved');
  }
  if (!addresses.length || addresses.some(({ address }) => !isPublicIp(address))) {
    throw new PublicUrlValidationError('Policy URL hostname must resolve only to public addresses');
  }

  return url;
}
