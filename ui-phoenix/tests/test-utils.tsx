/**
 * Test utilities — wraps components with providers needed for testing
 */

import { type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
}

interface WrapperProps {
  children: ReactNode;
  initialRoute?: string;
}

function TestWrapper({ children, initialRoute = "/" }: WrapperProps) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  );
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions & { initialRoute?: string }
) {
  const { initialRoute, ...renderOptions } = options ?? {};
  return render(ui, {
    wrapper: ({ children }) => (
      <TestWrapper initialRoute={initialRoute}>{children}</TestWrapper>
    ),
    ...renderOptions,
  });
}

export { render };
