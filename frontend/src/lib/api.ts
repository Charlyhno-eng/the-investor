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

/** Incremental newline-delimited JSON; handles arbitrary transport boundaries. */
export async function postStream<T>(
  path: string,
  data: unknown,
  signal: AbortSignal,
  onValue: (value: T) => void,
) {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    signal,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `Le calcul n’a pas démarré (${response.status}).`,
    );
  }
  if (!response.body) throw new Error("Flux de résultats indisponible.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop()!;
      for (const line of lines) if (line.trim()) onValue(JSON.parse(line) as T);
      if (done) {
        if (buffer.trim()) onValue(JSON.parse(buffer) as T);
        break;
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
