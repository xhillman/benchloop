import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getApiClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/server", () => ({
  getApiClient: getApiClientMock,
}));

import { AppShellProvider, useAppShellState } from "@/components/providers/app-shell-provider";
import { AppShell } from "@/components/shell/app-shell";
import DashboardPage from "@/app/(shell)/dashboard/page";
import ExperimentsPage from "@/app/(shell)/experiments/page";
import RunsPage from "@/app/(shell)/runs/page";
import SettingsPage from "@/app/(shell)/settings/page";

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
}));

const clerkState = vi.hoisted(() => ({
  signedIn: false,
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    getToken: vi.fn(async () => null),
    isSignedIn: clerkState.signedIn,
  }),
  UserButton: () => <button type="button">User menu</button>,
}));

function ShellStateHarness() {
  const { setGlobalError, startLoading } = useAppShellState();

  return (
    <div>
      <button onClick={startLoading} type="button">
        Trigger loading
      </button>
      <button
        onClick={() =>
          setGlobalError({
            title: "FastAPI request failed",
            detail: "Normalized API errors should surface here.",
          })
        }
        type="button"
      >
        Trigger error
      </button>
    </div>
  );
}

describe("product shell", () => {
  it("renders the primary product navigation", () => {
    clerkState.signedIn = false;

    render(
      <AppShellProvider>
        <AppShell>
          <div>Dashboard body</div>
        </AppShell>
      </AppShellProvider>,
    );

    expect(screen.getByRole("link", { name: /dashboard overview/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getByRole("link", { name: /experiments inputs/i })).toHaveAttribute(
      "href",
      "/experiments",
    );
    expect(screen.getByRole("link", { name: /runs history/i })).toHaveAttribute("href", "/runs");
    expect(screen.getByRole("link", { name: /settings defaults/i })).toHaveAttribute(
      "href",
      "/settings",
    );
    expect(screen.getByRole("link", { name: /sign in/i })).toHaveAttribute("href", "/sign-in");
  });

  it("surfaces shared loading and error banners from the global shell state", () => {
    clerkState.signedIn = false;

    render(
      <AppShellProvider>
        <AppShell>
          <ShellStateHarness />
        </AppShell>
      </AppShellProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /trigger loading/i }));
    fireEvent.click(screen.getByRole("button", { name: /trigger error/i }));

    expect(screen.getByText(/tracking 1 active shell operation/i)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/fastapi request failed/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/normalized api errors should surface here/i);
  });

  it("shows the signed-in shell affordance when a Clerk session exists", () => {
    clerkState.signedIn = true;

    render(
      <AppShellProvider>
        <AppShell>
          <div>Dashboard body</div>
        </AppShell>
      </AppShellProvider>,
    );

    expect(screen.getByRole("button", { name: /user menu/i })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /sign in/i })).not.toBeInTheDocument();
  });
});

describe("shell routes", () => {
  it("renders the dashboard page shell with API bootstrap data", async () => {
    getApiClientMock.mockResolvedValue({
      auth: {
        getMe: vi.fn(async () => ({
          external_user_id: "user_123",
        })),
      },
      health: {
        getStatus: vi.fn(async () => ({
          environment: "local",
          service: "benchloop-api",
          status: "ok",
        })),
      },
    });

    render(await DashboardPage());

    expect(screen.getByRole("heading", { level: 1, name: /experiment control plane/i })).toBeInTheDocument();
    expect(screen.getByText(/fastapi stays canonical/i)).toBeInTheDocument();
    expect(screen.getByText(/ok via benchloop-api/i)).toBeInTheDocument();
    expect(screen.getByText("user_123")).toBeInTheDocument();
  });

  it("renders placeholder shells for the remaining primary sections", () => {
    render(
      <div>
        <ExperimentsPage />
        <RunsPage />
      </div>,
    );

    expect(screen.getByRole("heading", { level: 1, name: /organize the work before you execute it/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /inspect output, latency, and reproducibility from one lane/i })).toBeInTheDocument();
  });

  it("renders the settings page shell with API-backed defaults", async () => {
    getApiClientMock.mockResolvedValue({
      settings: {
        get: vi.fn(async () => ({
          default_provider: "openai",
          default_model: "gpt-4.1-mini",
          timezone: "UTC",
        })),
        listCredentials: vi.fn(async () => []),
      },
    });

    render(<AppShellProvider>{await SettingsPage()}</AppShellProvider>);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /configure defaults and provider access/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue("gpt-4.1-mini")).toBeInTheDocument();
  });
});
