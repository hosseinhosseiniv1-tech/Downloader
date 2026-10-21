import { describe, expect, it, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import JobsPage from "../pages/admin/JobsPage";
import { installFetchMock, mockFetch, resetFetchMock } from "./msw";

function withProviders(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{node}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("AdminJobs — table", () => {
  afterEach(() => resetFetchMock());

  it("renders job rows and shows failed_upload_limit status", async () => {
    installFetchMock();
    mockFetch("/api/v1/jobs", async () =>
      new Response(
        JSON.stringify({
          items: [
            {
              id: "job-aaa",
              chat_id: 1,
              url: "https://youtube.com/x",
              quality: "1080p",
              status: "completed",
              platform: "youtube",
              filesize: 1000,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-01T00:01:00Z",
            },
            {
              id: "job-bbb",
              chat_id: 2,
              url: "https://youtube.com/y",
              quality: "best",
              status: "failed_upload_limit",
              platform: "youtube",
              filesize: 3_000_000_000,
              created_at: "2025-01-02T00:00:00Z",
              updated_at: "2025-01-02T00:01:00Z",
            },
          ],
          total: 2,
          page: 1,
          per_page: 25,
          total_pages: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );

    render(withProviders(<JobsPage apiKey="test-key" />));

    await waitFor(() => expect(screen.getByText("job-aaa")).toBeInTheDocument());
    expect(screen.getByText("job-bbb")).toBeInTheDocument();
    expect(screen.getByText("failed_upload_limit")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /view/i })).toHaveLength(2);
  });
});