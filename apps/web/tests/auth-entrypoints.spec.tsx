import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import HomePage from "@/app/(marketing)/page";
import SignInPage from "@/app/sign-in/[[...sign-in]]/page";

const authState = vi.hoisted(() => ({
  userId: null as null | string,
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: React.ReactNode }) => children,
  SignIn: () => <div>Clerk sign-in form</div>,
  SignUp: () => <div>Clerk sign-up form</div>,
}));

vi.mock("@clerk/nextjs/server", () => ({
  auth: vi.fn(async () => ({
    userId: authState.userId,
  })),
}));

vi.mock("next/navigation", async () => {
  const actual = await vi.importActual<typeof import("next/navigation")>("next/navigation");

  return {
    ...actual,
    redirect: vi.fn(),
  };
});

describe("marketing entrypoint", () => {
  it("routes signed-out visitors toward the sign-in flow", async () => {
    authState.userId = null;

    render(await HomePage());

    expect(screen.getByRole("link", { name: /sign in to benchloop/i })).toHaveAttribute(
      "href",
      "/sign-in",
    );
    expect(screen.getAllByText(/public visitor/i)).toHaveLength(2);
  });

  it("routes signed-in visitors toward the dashboard", async () => {
    authState.userId = "user_123";

    render(await HomePage());

    expect(screen.getByRole("link", { name: /open dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    expect(screen.getAllByText(/active clerk session/i)).toHaveLength(2);
  });
});

describe("auth routes", () => {
  it("renders the sign-in screen", async () => {
    authState.userId = null;

    render(await SignInPage());

    expect(screen.getByText(/clerk sign-in form/i)).toBeInTheDocument();
  });
});
