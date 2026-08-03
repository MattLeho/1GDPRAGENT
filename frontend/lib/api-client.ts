export interface StructuredApiError {
  error?: {
    code?: string;
    message?: string;
    reason?: string;
  };
  detail?: string;
  message?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly reason?: string;
  readonly handled: boolean;

  constructor(status: number, message: string, code = 'API_ERROR', reason?: string, handled = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.reason = reason;
    this.handled = handled;
  }
}

/**
 * Authentication failures are handled centrally by clearing protected state and
 * navigating to login. Feature-level catches must stay silent for that failure
 * and for companion requests cancelled by the same transition.
 */
export function shouldSuppressProtectedRequestError(error: unknown): boolean {
  if (error instanceof ApiError) return error.handled;
  return Boolean(
    error
    && typeof error === 'object'
    && 'name' in error
    && (error as { name?: unknown }).name === 'AbortError'
  );
}

type ProtectedStateReset = () => void;

const protectedStateResets = new Set<ProtectedStateReset>();
const protectedRequestControllers = new Set<AbortController>();
let authenticationFailureHandled = false;

export function registerProtectedStateReset(reset: ProtectedStateReset): () => void {
  protectedStateResets.add(reset);
  return () => protectedStateResets.delete(reset);
}

function isMutation(method: string | undefined): boolean {
  return !['GET', 'HEAD', 'OPTIONS'].includes((method ?? 'GET').toUpperCase());
}

async function responsePayload(response: Response): Promise<StructuredApiError | unknown> {
  if (response.status === 204) return undefined;
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return response.json().catch(() => undefined);
  }
  const text = await response.text().catch(() => '');
  return text ? { detail: text } : undefined;
}

function toApiError(response: Response, payload: unknown, handled = false): ApiError {
  const body = (payload && typeof payload === 'object' ? payload : {}) as StructuredApiError;
  const message = body.error?.message ?? body.detail ?? body.message ?? `Request failed (${response.status})`;
  return new ApiError(
    response.status,
    message,
    body.error?.code ?? (response.status === 401 ? 'AUTHENTICATION_REQUIRED' : 'API_ERROR'),
    body.error?.reason,
    handled,
  );
}

function handleAuthenticationFailure(payload: unknown): boolean {
  if (authenticationFailureHandled || typeof window === 'undefined') return authenticationFailureHandled;
  authenticationFailureHandled = true;
  for (const controller of protectedRequestControllers) controller.abort('authentication-failed');
  clearProtectedState();
  const body = (payload && typeof payload === 'object' ? payload : {}) as StructuredApiError;
  const reason = body.error?.reason ?? body.error?.code ?? 'session_invalid';
  const target = `/login?reason=${encodeURIComponent(reason)}`;
  window.location.assign(target);
  return true;
}

function clearProtectedState(): void {
  for (const reset of protectedStateResets) {
    try {
      reset();
    } catch {
      // A failing feature store must not block the global authentication transition.
    }
  }
  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new Event('gdpr:protected-state-cleared'));
  }
}

function protectedRequestInit(init: RequestInit): RequestInit {
  const headers = new Headers(init.headers);
  if (isMutation(init.method)) headers.set('x-gdpr-csrf', '1');
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has('content-type')) {
    headers.set('content-type', 'application/json');
  }
  return {
    ...init,
    headers,
    credentials: 'same-origin',
    cache: init.cache ?? 'no-store',
  };
}

export async function protectedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  if (authenticationFailureHandled) {
    throw new ApiError(401, 'Authentication transition is already in progress', 'AUTHENTICATION_REQUIRED', 'session_invalid', true);
  }
  const controller = new AbortController();
  protectedRequestControllers.add(controller);
  const callerSignal = init.signal;
  const signal = callerSignal
    ? AbortSignal.any([controller.signal, callerSignal])
    : controller.signal;
  try {
    const response = await fetch(input, protectedRequestInit({ ...init, signal }));
    if (response.status === 401) {
      const payload = await response.clone().json().catch(() => undefined);
      const handled = handleAuthenticationFailure(payload);
      throw toApiError(response, payload, handled);
    }
    return response;
  } finally {
    protectedRequestControllers.delete(controller);
  }
}

export async function protectedApi<T>(input: RequestInfo | URL, init: RequestInit = {}): Promise<T> {
  const response = await protectedFetch(input, init);
  const payload = await responsePayload(response);
  if (!response.ok) throw toApiError(response, payload);
  return payload as T;
}

export async function logout(): Promise<void> {
  await protectedApi('/api/auth/logout', { method: 'POST' });
  clearProtectedState();
  authenticationFailureHandled = true;
  if (typeof window !== 'undefined') window.location.assign('/login?reason=logged_out');
}

export function resetAuthenticationFailureForTests(): void {
  for (const controller of protectedRequestControllers) controller.abort('test-reset');
  protectedRequestControllers.clear();
  authenticationFailureHandled = false;
}
