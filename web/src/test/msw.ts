import { vi } from "vitest";

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

const handlers = new Map<string, Handler>();

export function mockFetch(path: string, handler: Handler) {
  handlers.set(path, handler);
}

export function installFetchMock() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      for (const [path, handler] of handlers) {
        if (url.endsWith(path) || url.includes(path)) {
          return handler(url, init);
        }
      }
      return new Response(JSON.stringify({ error: "not_mocked" }), { status: 404 });
    })
  );
}

export function resetFetchMock() {
  handlers.clear();
  vi.unstubAllGlobals();
}