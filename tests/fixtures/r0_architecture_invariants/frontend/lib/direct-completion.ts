export async function unsafeDirectCompletion() {
  return fetch('https://api.openai.com/v1/chat/completions', { method: 'POST' });
}
