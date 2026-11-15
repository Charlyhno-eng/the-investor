import { afterEach, expect, it, vi } from "vitest";
import { postStream } from "../../src/lib/api";

afterEach(() => vi.unstubAllGlobals());
it("decodes progressively across split UTF-8 and JSON transport chunks", async () => {
  const bytes = new TextEncoder().encode(
    '{"label":"Égalité"}\n{"completed":1}\n{"completed":2}',
  );
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(bytes.slice(0, 11));
      controller.enqueue(bytes.slice(11, 20));
      controller.enqueue(bytes.slice(20));
      controller.close();
    },
  });
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(stream)));
  const received: unknown[] = [];
  await postStream("/test", {}, new AbortController().signal, (value) =>
    received.push(value),
  );
  expect(received).toEqual([
    { label: "Égalité" },
    { completed: 1 },
    { completed: 2 },
  ]);
});
it("surfaces HTTP errors before reading a result stream", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Indisponible" }), {
        status: 503,
      }),
    ),
  );
  await expect(
    postStream("/test", {}, new AbortController().signal, () => undefined),
  ).rejects.toThrow("Indisponible");
});
