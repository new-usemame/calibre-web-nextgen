/* Typed fetch helpers — same-origin, credentials included. */

export interface Me {
  id: number;
  name: string;
  locale: string;
  theme: string;
  role: Record<string, boolean>;
}

export interface Book {
  id: number;
  title: string;
  authors: string[];
  series: string | null;
  series_index: number | null;
  cover_url: string | null;
  formats: string[];
  read?: boolean;
  archived?: boolean;
}

export interface BookFormat {
  format: string;
  size_bytes: number;
  download_url: string;
  read_url: string;
}

export interface BookDetail {
  id: number;
  title: string;
  authors: string[];
  series: string | null;
  series_index: string;
  cover_url: string | null;
  pubdate: string | null;
  description_html: string | null;
  tags: string[];
  languages: string[];
  publishers: string[];
  identifiers: { type: string; val: string }[];
  formats: BookFormat[];
  read: boolean;
  archived: boolean;
}

export interface BooksPage {
  items: Book[];
  page: number;
  per_page: number;
  total: number;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

let _csrfCache: string | null = null;

export async function getCsrf(): Promise<string> {
  if (_csrfCache) return _csrfCache;
  const res = await fetch('/api/v1/auth/csrf', { credentials: 'include' });
  if (!res.ok) throw new ApiError(res.status, 'Failed to fetch CSRF token');
  const data = await res.json() as { csrf_token: string };
  _csrfCache = data.csrf_token;
  return _csrfCache;
}

function clearCsrf() {
  _csrfCache = null;
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(path, { credentials: 'include' });
  if (!res.ok) {
    let msg = res.statusText;
    try { const d = await res.json() as { error?: string }; msg = d.error ?? msg; } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const doPost = async (csrf: string): Promise<Response> => {
    return fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let csrf = await getCsrf();
  let res = await doPost(csrf);

  if (res.status === 400) {
    clearCsrf();
    csrf = await getCsrf();
    res = await doPost(csrf);
  }

  if (!res.ok) {
    let msg = res.statusText;
    try { const d = await res.json() as { error?: string }; msg = d.error ?? msg; } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}
