export const apiBase = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api').replace(/\/$/, '');
export function apiUrl(path: string): string { return `${apiBase}${path.startsWith('/') ? path : `/${path}`}`; }

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const body = await response.json(); message = body.detail ?? message; }
    catch { try { message = (await response.text()) || message; } catch { /* keep status fallback */ } }
    throw new Error(message);
  }
  return response.json();
}
