export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item: { msg: string }) => item.msg).join(" · ")
          : `Le serveur ne répond pas (${response.status}).`,
    );
  }
  return body as T;
}
export function post<T>(path: string, data: unknown, signal?: AbortSignal) {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal,
  });
}
