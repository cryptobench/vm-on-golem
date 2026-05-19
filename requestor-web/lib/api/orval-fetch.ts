export type ApiRequestOptions = RequestInit & {
  baseUrl?: string;
  queryParams?: Record<string, string | number | boolean | null | undefined>;
};

export async function orvalFetch<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { baseUrl, queryParams, ...init } = options;
  const url = buildUrl(baseUrl, path, queryParams);
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

function buildUrl(
  baseUrl: string | undefined,
  path: string,
  queryParams?: ApiRequestOptions["queryParams"],
): string {
  const url = baseUrl
    ? new URL(`${baseUrl.replace(/\/$/, "")}/${path.replace(/^\//, "")}`)
    : new URL(path, window.location.origin);

  Object.entries(queryParams || {}).forEach(([key, value]) => {
    if (value == null || url.searchParams.has(key)) return;
    url.searchParams.set(key, String(value));
  });

  if (!baseUrl) {
    return `${url.pathname}${url.search}`;
  }
  return url.toString();
}
