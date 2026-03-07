import { act, fireEvent, renderHook, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "@/lib/api";
import { useRunWorkbench } from "@/hooks/use-mutations";
import { useJobsStore } from "@/stores/jobs-store";
import { SourcesPage } from "@/features/sources/sources-page";
import * as mutations from "@/hooks/use-mutations";
import { renderWithProviders } from "../test-utils";

function makeWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("QA independent review", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useJobsStore.setState({ jobs: {} });
  });

  it("shows SourcesPage still passes mutate callbacks, so page-level toast ownership remains", async () => {
    const mutate = vi.fn();
    vi.spyOn(mutations, "useRunSourceCheck").mockReturnValue({
      mutate,
      isPending: false,
      data: undefined,
    } as never);

    renderWithProviders(<SourcesPage />);
    fireEvent.click(screen.getByRole("button", { name: /check sources/i }));

    expect(mutate).toHaveBeenCalledTimes(1);
    const [, options] = mutate.mock.calls[0];
    expect(options).toMatchObject({
      onError: expect.any(Function),
      onSuccess: expect.any(Function),
    });
  });

  it("does not register a backend job for workbench mutations", async () => {
    const spy = vi.spyOn(api, "runWorkbench").mockImplementation(async () => {
      return {
        profile: {},
        template: {},
        deterministic: { markdown: "# Det", section_word_usage: {} },
        ai: { markdown: "# AI", section_word_usage: {} },
      };
    });

    const { result } = renderHook(() => useRunWorkbench(), { wrapper: makeWrapper() });

    await act(async () => {
      await result.current.mutateAsync({ template: "default" });
    });

    expect(spy).toHaveBeenCalledWith({ template: "default" });
    expect(useJobsStore.getState().jobs["workbench-job-id"]).toBeUndefined();
  });
});
