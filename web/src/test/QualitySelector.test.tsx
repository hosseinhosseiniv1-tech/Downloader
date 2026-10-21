import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import Landing from "../pages/Landing";
import { installFetchMock, mockFetch, resetFetchMock } from "./msw";

function withProviders(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{node}</QueryClientProvider>;
}

describe("Landing — quality selector", () => {
  beforeEach(() => {
    installFetchMock();
    mockFetch("/api/v1/identify", async () =>
      new Response(
        JSON.stringify({
          title: "Test Video",
          uploader: "tester",
          available_qualities: ["best", "720p", "480p", "audio"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
  });

  afterEach(() => {
    resetFetchMock();
    vi.clearAllMocks();
  });

  it("renders quality options after identify", async () => {
    render(withProviders(<Landing />));

    fireEvent.change(screen.getByLabelText(/Paste a video URL/i), {
      target: { value: "https://example.com/v" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Fetch metadata/i }));

    await waitFor(() => expect(screen.getByText("Test Video")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: /✨ Best/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /🎥 720p/i })).toBeInTheDocument();

    // 1080p is not in available_qualities → disabled.
    const hd = screen.getByRole("button", { name: /🎥 1080p/i });
    expect(hd).toBeDisabled();
  });
});