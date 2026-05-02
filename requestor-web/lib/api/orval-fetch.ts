export type ApiRequestOptions = RequestInit & {
  baseUrl?: string;
};

export async function orvalFetch<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { baseUrl, ...init } = options;
  const url = buildUrl(baseUrl, path);
  const response = await fetch(url, {
    ...init,
  });
  const text = [204, 205, 304].includes(response.status)
    ? ""
    : await response.text();
  const data = text ? JSON.parse(text) : null;

  return {
    data,
    status: response.status,
    headers: response.headers,
  } as T;
}

function buildUrl(baseUrl: string | undefined, path: string): string {
  const url = baseUrl
    ? new URL(`${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`)
    : new URL(path, window.location.origin);

  if (!baseUrl) {
    return `${url.pathname}${url.search}`;
  }
  return url.toString();
}
