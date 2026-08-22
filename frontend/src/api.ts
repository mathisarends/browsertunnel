const API_PREFIX = "/api";

/** Calls the separately running backend through Vite's development proxy. */
export async function getJson<T>(path: string): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_PREFIX}${normalizedPath}`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as T;
}
