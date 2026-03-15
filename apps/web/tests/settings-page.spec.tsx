import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getApiClientMock = vi.hoisted(() => vi.fn());
const useApiClientMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/server", () => ({
  getApiClient: getApiClientMock,
}));

vi.mock("@/lib/api/browser", () => ({
  useApiClient: useApiClientMock,
}));

import SettingsPage from "@/app/(shell)/settings/page";
import { AppShellProvider } from "@/components/providers/app-shell-provider";
import { SettingsWorkspace } from "@/components/settings/settings-workspace";

function buildBrowserClientMock() {
  return {
    settings: {
      createCredential: vi.fn(),
      deleteCredential: vi.fn(),
      get: vi.fn(),
      listCredentials: vi.fn(),
      replaceCredential: vi.fn(),
      update: vi.fn(),
      validateCredential: vi.fn(),
    },
  };
}

describe("settings page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useApiClientMock.mockReturnValue(buildBrowserClientMock());
  });

  it("renders defaults and masked credentials from the API bootstrap", async () => {
    getApiClientMock.mockResolvedValue({
      settings: {
        get: vi.fn(async () => ({
          default_provider: "openai",
          default_model: "gpt-4.1-mini",
          timezone: "UTC",
        })),
        listCredentials: vi.fn(async () => [
          {
            id: "cred_1",
            provider: "anthropic",
            key_label: "Primary key",
            masked_api_key: "••••4321",
            validation_status: "valid",
            last_validated_at: "2025-01-02T00:00:00Z",
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          },
        ]),
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
    expect(screen.getByText("Primary key")).toBeInTheDocument();
    expect(screen.getByText("••••4321")).toBeInTheDocument();
    expect(screen.getByText(/^Valid$/)).toBeInTheDocument();
  });
});

describe("settings workspace", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("updates default provider, model, and timezone", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.settings.update.mockResolvedValue({
      default_provider: "anthropic",
      default_model: "claude-3-5-sonnet",
      timezone: "America/New_York",
    });
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <SettingsWorkspace
          initialCredentials={[]}
          initialSettings={{
            default_provider: "openai",
            default_model: "gpt-4.1-mini",
            timezone: "UTC",
          }}
        />
      </AppShellProvider>,
    );

    fireEvent.change(screen.getByLabelText(/default provider/i), {
      target: { value: "anthropic" },
    });
    fireEvent.change(screen.getByLabelText(/default model/i), {
      target: { value: "claude-3-5-sonnet" },
    });
    fireEvent.change(screen.getByLabelText(/timezone/i), {
      target: { value: "America/New_York" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save defaults/i }));

    await waitFor(() => {
      expect(browserClient.settings.update).toHaveBeenCalledWith({
        default_provider: "anthropic",
        default_model: "claude-3-5-sonnet",
        timezone: "America/New_York",
      });
    });
    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/default preferences saved/i);
    });
  });

  it("creates, validates, replaces, and deletes credentials", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.settings.validateCredential.mockResolvedValue({
      id: "cred_1",
      provider: "openai",
      key_label: "Primary key",
      masked_api_key: "••••1234",
      validation_status: "valid",
      last_validated_at: "2025-01-02T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-02T00:00:00Z",
    });
    browserClient.settings.replaceCredential.mockResolvedValue({
      id: "cred_1",
      provider: "openai",
      key_label: "Rotated key",
      masked_api_key: "••••5678",
      validation_status: "not_validated",
      last_validated_at: null,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-03T00:00:00Z",
    });
    browserClient.settings.deleteCredential.mockResolvedValue(undefined);
    browserClient.settings.createCredential.mockResolvedValue({
      id: "cred_2",
      provider: "anthropic",
      key_label: "Fallback",
      masked_api_key: "••••9999",
      validation_status: "not_validated",
      last_validated_at: null,
      created_at: "2025-01-04T00:00:00Z",
      updated_at: "2025-01-04T00:00:00Z",
    });
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <SettingsWorkspace
          initialCredentials={[
            {
              id: "cred_1",
              provider: "openai",
              key_label: "Primary key",
              masked_api_key: "••••1234",
              validation_status: "not_validated",
              last_validated_at: null,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-01T00:00:00Z",
            },
          ]}
          initialSettings={{
            default_provider: null,
            default_model: null,
            timezone: "UTC",
          }}
        />
      </AppShellProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate key/i }));

    await waitFor(() => {
      expect(browserClient.settings.validateCredential).toHaveBeenCalledWith("cred_1");
    });
    await waitFor(() => {
      expect(screen.getByText(/validated successfully/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /replace key/i }));
    fireEvent.change(screen.getByLabelText(/replacement label/i), {
      target: { value: "Rotated key" },
    });
    fireEvent.change(screen.getByLabelText(/new api key/i), {
      target: { value: "sk-new-secret-5678" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save replacement/i }));

    await waitFor(() => {
      expect(browserClient.settings.replaceCredential).toHaveBeenCalledWith("cred_1", {
        api_key: "sk-new-secret-5678",
        key_label: "Rotated key",
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Rotated key")).toBeInTheDocument();
      expect(screen.getByText("••••5678")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /delete key/i }));

    await waitFor(() => {
      expect(browserClient.settings.deleteCredential).toHaveBeenCalledWith("cred_1");
    });
    await waitFor(() => {
      expect(screen.queryByText("Rotated key")).not.toBeInTheDocument();
    });

    fireEvent.change(screen.getByLabelText(/credential provider/i), {
      target: { value: "anthropic" },
    });
    fireEvent.change(screen.getByLabelText(/^label$/i), {
      target: { value: "Fallback" },
    });
    fireEvent.change(screen.getByLabelText(/^api key$/i), {
      target: { value: "sk-ant-secret-9999" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add credential/i }));

    await waitFor(() => {
      expect(browserClient.settings.createCredential).toHaveBeenCalledWith({
        provider: "anthropic",
        key_label: "Fallback",
        api_key: "sk-ant-secret-9999",
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Fallback")).toBeInTheDocument();
      expect(screen.getByText("••••9999")).toBeInTheDocument();
    });
  });
});
