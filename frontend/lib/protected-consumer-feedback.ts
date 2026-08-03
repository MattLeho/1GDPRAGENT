import { shouldSuppressProtectedRequestError } from './api-client';

/**
 * Shared feature-consumer boundary: authentication transitions are already
 * presented by the shell redirect, so consumers report only ordinary failures.
 */
export function reportProtectedConsumerError(
  error: unknown,
  report: (error: unknown) => void,
): boolean {
  if (shouldSuppressProtectedRequestError(error)) return false;
  report(error);
  return true;
}
