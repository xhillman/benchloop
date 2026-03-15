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

import RunsPage from "@/app/(shell)/runs/page";
import RunDetailPage from "@/app/(shell)/runs/[runId]/page";
import { AppShellProvider } from "@/components/providers/app-shell-provider";
import { RunsWorkspace } from "@/components/runs/runs-workspace";

function buildRun(id: string, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id,
    experiment_id: "exp_1",
    experiment_name: "Support triage",
    test_case_id: `case_${id}`,
    config_id: `cfg_${id}`,
    config_name: "Refund baseline",
    config_version_label: "v1",
    test_case_input_preview: "Refund the duplicate charge.",
    status: "completed",
    provider: "openai",
    model: "gpt-4.1-mini",
    workflow_mode: "single_shot",
    tags: ["priority"],
    latency_ms: 240,
    estimated_cost_usd: 0.0014,
    created_at: "2025-01-10T15:00:00Z",
    started_at: "2025-01-10T15:00:00Z",
    finished_at: "2025-01-10T15:00:02Z",
    ...overrides,
  };
}

function buildBrowserClientMock() {
  return {
    runs: {
      get: vi.fn(),
      list: vi.fn(),
    },
  };
}

function buildRunDetail(id: string, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id,
    experiment_id: "exp_1",
    experiment_name: "Support triage",
    test_case_id: "case_1",
    config_id: "cfg_1",
    credential_id: null,
    status: "completed",
    provider: "openai",
    model: "gpt-4.1-mini",
    workflow_mode: "single_shot",
    config_snapshot: {
      config_id: "cfg_1",
      name: "Refund baseline",
      version_label: "v1",
      description: "Direct support response.",
      provider: "openai",
      model: "gpt-4.1-mini",
      workflow_mode: "single_shot",
      system_prompt_template: "You are a billing assistant.",
      rendered_system_prompt: "You are a billing assistant.",
      user_prompt_template: "Respond to {{input}}",
      rendered_user_prompt: "Respond to Refund the duplicate charge.",
      temperature: 0.2,
      max_output_tokens: 256,
      top_p: 0.9,
      context_bundle_id: null,
      tags: ["priority"],
      is_baseline: true,
    },
    input_snapshot: {
      test_case_id: "case_1",
      input_text: "Refund the duplicate charge.",
      expected_output_text: "Acknowledge the refund.",
      notes: "Priority billing case.",
      tags: ["priority", "refund"],
    },
    context_snapshot: {
      source: "inline",
      bundle_id: null,
      name: "Refund policy excerpt",
      content_text: "Refunds clear within 5 business days.",
      notes: "Ground the answer in policy.",
    },
    output_text: "Refund confirmed within five business days.",
    error_message: null,
    usage_input_tokens: 44,
    usage_output_tokens: 12,
    usage_total_tokens: 56,
    latency_ms: 240,
    estimated_cost_usd: 0.0014,
    created_at: "2025-01-10T15:00:00Z",
    started_at: "2025-01-10T15:00:00Z",
    finished_at: "2025-01-10T15:00:02Z",
    updated_at: "2025-01-10T15:00:02Z",
    ...overrides,
  };
}

describe("runs page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders run history from the API bootstrap", async () => {
    getApiClientMock.mockResolvedValue({
      runs: {
        list: vi.fn(async () => [buildRun("run_1")]),
      },
      experiments: {
        list: vi.fn(async () => [
          {
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          },
        ]),
      },
    });
    useApiClientMock.mockReturnValue(buildBrowserClientMock());

    render(<AppShellProvider>{await RunsPage()}</AppShellProvider>);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /keep the execution record sortable, filterable, and reproducible/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Support triage")).toHaveLength(2);
    expect(screen.getAllByText(/refund baseline v1/i)).toHaveLength(2);
    expect(screen.getByRole("link", { name: /open detail for refund baseline v1/i })).toHaveAttribute(
      "href",
      "/runs/run_1",
    );
  });
});

describe("runs workspace", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("applies filters through the shared browser client", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.runs.list.mockResolvedValueOnce([
      buildRun("run_2", {
        config_id: "cfg_2",
        config_name: "Escalation variant",
        config_version_label: "v2",
        model: "gpt-4.1-nano",
        latency_ms: 120,
      }),
    ]);
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <RunsWorkspace
          initialExperiments={[
            {
              id: "exp_1",
              name: "Support triage",
              description: "Compare prompt variants for support tickets.",
              tags: ["support"],
              is_archived: false,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
          initialRuns={[buildRun("run_1")]}
        />
      </AppShellProvider>,
    );

    fireEvent.change(screen.getByLabelText(/^provider$/i), {
      target: { value: "openai" },
    });
    fireEvent.change(screen.getByLabelText(/^tag$/i), {
      target: { value: "priority" },
    });
    fireEvent.change(screen.getByLabelText(/^sort by$/i), {
      target: { value: "fastest" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await waitFor(() => {
      expect(browserClient.runs.list).toHaveBeenCalledWith({
        experimentIds: [],
        configIds: [],
        providers: ["openai"],
        models: [],
        statuses: [],
        tags: ["priority"],
        createdFrom: null,
        createdTo: null,
        sortBy: "latency_ms",
        sortOrder: "asc",
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/escalation variant v2/i)).toBeInTheDocument();
    });
  });
});

describe("run detail page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders immutable run detail from the API bootstrap", async () => {
    getApiClientMock.mockResolvedValue({
      runs: {
        get: vi.fn(async () => buildRunDetail("run_1")),
      },
    });

    render(
      await RunDetailPage({
        params: Promise.resolve({
          runId: "run_1",
        }),
      }),
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /inspect the immutable record behind one execution/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText(/support triage via openai/i)).toBeInTheDocument();
    expect(screen.getByText(/respond to refund the duplicate charge\./i)).toBeInTheDocument();
    expect(screen.getByText(/refunds clear within 5 business days\./i)).toBeInTheDocument();
    expect(screen.getByText(/refund confirmed within five business days\./i)).toBeInTheDocument();
  });
});
