import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getApiClientMock = vi.hoisted(() => vi.fn());
const useApiClientMock = vi.hoisted(() => vi.fn());
const pushMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/server", () => ({
  getApiClient: getApiClientMock,
}));

vi.mock("@/lib/api/browser", () => ({
  useApiClient: useApiClientMock,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

import ExperimentDetailPage from "@/app/(shell)/experiments/[experimentId]/page";
import ExperimentsPage from "@/app/(shell)/experiments/page";
import { AppShellProvider } from "@/components/providers/app-shell-provider";
import { ExperimentDetailShell } from "@/components/experiments/experiment-detail-shell";
import { ExperimentsWorkspace } from "@/components/experiments/experiments-workspace";

function buildBrowserClientMock() {
  return {
    experiments: {
      cloneConfig: vi.fn(),
      launchBatchRuns: vi.fn(),
      launchRun: vi.fn(),
      createConfig: vi.fn(),
      create: vi.fn(),
      createTestCase: vi.fn(),
      deleteConfig: vi.fn(),
      delete: vi.fn(),
      deleteTestCase: vi.fn(),
      duplicateTestCase: vi.fn(),
      get: vi.fn(),
      listConfigs: vi.fn(),
      list: vi.fn(),
      listTestCases: vi.fn(),
      markConfigBaseline: vi.fn(),
      updateConfig: vi.fn(),
      updateTestCase: vi.fn(),
      update: vi.fn(),
    },
  };
}

describe("experiments page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    useApiClientMock.mockReturnValue(buildBrowserClientMock());
  });

  it("renders experiments from the API bootstrap", async () => {
    getApiClientMock.mockResolvedValue({
      experiments: {
        list: vi.fn(async () => [
          {
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support", "triage"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          },
        ]),
      },
    });

    render(<AppShellProvider>{await ExperimentsPage()}</AppShellProvider>);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /organize the work before you execute it/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Support triage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open detail/i })).toHaveAttribute(
      "href",
      "/experiments/exp_1",
    );
  });

  it("creates experiments and applies API-backed filters", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.experiments.list
      .mockResolvedValueOnce([
        {
          id: "exp_1",
          name: "Support triage",
          description: "Compare prompt variants for support tickets.",
          tags: ["support", "triage"],
          is_archived: false,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-02T00:00:00Z",
        },
      ])
      .mockResolvedValueOnce([
        {
          id: "exp_2",
          name: "Sales follow-up",
          description: "Warm outbound reply variants.",
          tags: ["sales"],
          is_archived: false,
          created_at: "2025-01-03T00:00:00Z",
          updated_at: "2025-01-03T00:00:00Z",
        },
      ]);
    browserClient.experiments.create.mockResolvedValue({
      id: "exp_2",
      name: "Sales follow-up",
      description: "Warm outbound reply variants.",
      tags: ["sales"],
      is_archived: false,
      created_at: "2025-01-03T00:00:00Z",
      updated_at: "2025-01-03T00:00:00Z",
    });
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <ExperimentsWorkspace
          initialExperiments={[
            {
              id: "exp_1",
              name: "Support triage",
              description: "Compare prompt variants for support tickets.",
              tags: ["support", "triage"],
              is_archived: false,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
        />
      </AppShellProvider>,
    );

    fireEvent.change(screen.getByLabelText(/search by name/i), {
      target: { value: "support" },
    });
    fireEvent.click(screen.getByRole("button", { name: /apply filters/i }));

    await waitFor(() => {
      expect(browserClient.experiments.list).toHaveBeenCalledWith({
        search: "support",
        tags: [],
        includeArchived: false,
      });
    });

    fireEvent.change(screen.getByLabelText(/^name$/i), {
      target: { value: "Sales follow-up" },
    });
    fireEvent.change(screen.getByLabelText(/^description$/i), {
      target: { value: "Warm outbound reply variants." },
    });
    fireEvent.change(screen.getByLabelText(/^tags$/i), {
      target: { value: "sales" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create experiment/i }));

    await waitFor(() => {
      expect(browserClient.experiments.create).toHaveBeenCalledWith({
        name: "Sales follow-up",
        description: "Warm outbound reply variants.",
        tags: ["sales"],
      });
    });
    await waitFor(() => {
      expect(browserClient.experiments.list).toHaveBeenLastCalledWith();
    });
    await waitFor(() => {
      expect(screen.getByText("Sales follow-up")).toBeInTheDocument();
    });
  });

  it("renders the detail route shell from API bootstrap data", async () => {
    getApiClientMock.mockResolvedValue({
      experiments: {
        get: vi.fn(async () => ({
          id: "exp_1",
          name: "Support triage",
          description: "Compare prompt variants for support tickets.",
          tags: ["support", "triage"],
          is_archived: false,
          created_at: "2025-01-01T00:00:00Z",
          updated_at: "2025-01-02T00:00:00Z",
        })),
        listTestCases: vi.fn(async () => [
          {
            id: "case_1",
            experiment_id: "exp_1",
            input_text: "Customer asks for a refund after duplicate billing.",
            expected_output_text: "Acknowledge the issue and request account details.",
            notes: "Baseline support case.",
            tags: ["billing", "refund"],
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          },
        ]),
        listConfigs: vi.fn(async () => [
          {
            id: "cfg_1",
            experiment_id: "exp_1",
            name: "Direct answer",
            version_label: "v1",
            description: "Fast baseline answer.",
            provider: "openai",
            model: "gpt-4.1-mini",
            workflow_mode: "single_shot",
            system_prompt: "You are a support assistant.",
            user_prompt_template: "Reply to this ticket: {{ input_text }}",
            temperature: 0.2,
            max_output_tokens: 400,
            top_p: 0.9,
            context_bundle_id: null,
            tags: ["cheap", "fast"],
            is_baseline: true,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          },
        ]),
      },
    });

    render(
      <AppShellProvider>
        {await ExperimentDetailPage({
          params: Promise.resolve({ experimentId: "exp_1" }),
        })}
      </AppShellProvider>,
    );

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: /use one shell to steer the rest of the experiment workflow/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /overview/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});

describe("experiment detail shell", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("updates and deletes an experiment", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.experiments.update.mockResolvedValue({
      id: "exp_1",
      name: "Support triage revised",
      description: "Updated notes",
      tags: ["support", "v2"],
      is_archived: true,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-04T00:00:00Z",
    });
    browserClient.experiments.listConfigs.mockResolvedValue([]);
    browserClient.experiments.createTestCase.mockResolvedValue({
      id: "case_2",
      experiment_id: "exp_1",
      input_text: "Route an urgent refund request for review.",
      expected_output_text: "Acknowledge urgency and gather account details.",
      notes: "Escalation scenario.",
      tags: ["refund", "urgent"],
      created_at: "2025-01-05T00:00:00Z",
      updated_at: "2025-01-05T00:00:00Z",
    });
    browserClient.experiments.updateTestCase.mockResolvedValue({
      id: "case_1",
      experiment_id: "exp_1",
      input_text: "Customer asks for a refund after duplicate billing.",
      expected_output_text: "Acknowledge the duplicate charge and gather account details.",
      notes: "Baseline support case revised.",
      tags: ["billing", "refund", "priority"],
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-06T00:00:00Z",
    });
    browserClient.experiments.duplicateTestCase.mockResolvedValue({
      id: "case_3",
      experiment_id: "exp_1",
      input_text: "Customer asks for a refund after duplicate billing.",
      expected_output_text: "Acknowledge the issue and request account details.",
      notes: "Baseline support case.",
      tags: ["billing", "refund"],
      created_at: "2025-01-07T00:00:00Z",
      updated_at: "2025-01-07T00:00:00Z",
    });
    browserClient.experiments.deleteTestCase.mockResolvedValue(undefined);
    browserClient.experiments.delete.mockResolvedValue(undefined);
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <ExperimentDetailShell
          initialExperiment={{
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support", "triage"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          }}
          initialConfigs={[]}
          initialTestCases={[
            {
              id: "case_1",
              experiment_id: "exp_1",
              input_text: "Customer asks for a refund after duplicate billing.",
              expected_output_text: "Acknowledge the issue and request account details.",
              notes: "Baseline support case.",
              tags: ["billing", "refund"],
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
        />
      </AppShellProvider>,
    );

    fireEvent.change(screen.getByLabelText(/^name$/i), {
      target: { value: "Support triage revised" },
    });
    fireEvent.change(screen.getByLabelText(/^description$/i), {
      target: { value: "Updated notes" },
    });
    fireEvent.change(screen.getByLabelText(/^tags$/i), {
      target: { value: "support, v2" },
    });
    fireEvent.click(screen.getByLabelText(/archive this experiment/i));
    fireEvent.click(screen.getByRole("button", { name: /save experiment/i }));

    await waitFor(() => {
      expect(browserClient.experiments.update).toHaveBeenCalledWith("exp_1", {
        name: "Support triage revised",
        description: "Updated notes",
        tags: ["support", "v2"],
        is_archived: true,
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /delete experiment/i }));

    await waitFor(() => {
      expect(browserClient.experiments.delete).toHaveBeenCalledWith("exp_1");
    });
    await waitFor(() => {
      expect(pushMock).toHaveBeenCalledWith("/experiments");
    });
  });

  it("creates, edits, duplicates, selects, and deletes test cases from the detail tab", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.experiments.createTestCase.mockResolvedValue({
      id: "case_2",
      experiment_id: "exp_1",
      input_text: "Route an urgent refund request for review.",
      expected_output_text: "Acknowledge urgency and gather account details.",
      notes: "Escalation scenario.",
      tags: ["refund", "urgent"],
      created_at: "2025-01-05T00:00:00Z",
      updated_at: "2025-01-05T00:00:00Z",
    });
    browserClient.experiments.updateTestCase.mockResolvedValue({
      id: "case_1",
      experiment_id: "exp_1",
      input_text: "Customer asks for a refund after duplicate billing.",
      expected_output_text: "Acknowledge the duplicate charge and gather account details.",
      notes: "Baseline support case revised.",
      tags: ["billing", "refund", "priority"],
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-06T00:00:00Z",
    });
    browserClient.experiments.duplicateTestCase.mockResolvedValue({
      id: "case_3",
      experiment_id: "exp_1",
      input_text: "Customer asks for a refund after duplicate billing.",
      expected_output_text: "Acknowledge the issue and request account details.",
      notes: "Baseline support case.",
      tags: ["billing", "refund"],
      created_at: "2025-01-07T00:00:00Z",
      updated_at: "2025-01-07T00:00:00Z",
    });
    browserClient.experiments.deleteTestCase.mockResolvedValue(undefined);
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <ExperimentDetailShell
          initialExperiment={{
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support", "triage"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          }}
          initialConfigs={[]}
          initialTestCases={[
            {
              id: "case_1",
              experiment_id: "exp_1",
              input_text: "Customer asks for a refund after duplicate billing.",
              expected_output_text: "Acknowledge the issue and request account details.",
              notes: "Baseline support case.",
              tags: ["billing", "refund"],
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
        />
      </AppShellProvider>,
    );

    fireEvent.click(screen.getByRole("tab", { name: /test cases/i }));

    expect(screen.getByText(/selection-ready list/i)).toBeInTheDocument();
    expect(screen.getByText(/0 selected/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/input text/i), {
      target: { value: "Route an urgent refund request for review." },
    });
    fireEvent.change(screen.getByLabelText(/expected output/i), {
      target: { value: "Acknowledge urgency and gather account details." },
    });
    fireEvent.change(screen.getByLabelText(/notes/i), {
      target: { value: "Escalation scenario." },
    });
    fireEvent.change(screen.getByLabelText(/test case tags/i), {
      target: { value: "refund, urgent" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create test case/i }));

    await waitFor(() => {
      expect(browserClient.experiments.createTestCase).toHaveBeenCalledWith("exp_1", {
        input_text: "Route an urgent refund request for review.",
        expected_output_text: "Acknowledge urgency and gather account details.",
        notes: "Escalation scenario.",
        tags: ["refund", "urgent"],
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/1 selected/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /edit test case/i })[1]!);
    fireEvent.change(screen.getByLabelText(/expected output/i), {
      target: { value: "Acknowledge the duplicate charge and gather account details." },
    });
    fireEvent.change(screen.getByLabelText(/notes/i), {
      target: { value: "Baseline support case revised." },
    });
    fireEvent.change(screen.getByLabelText(/test case tags/i), {
      target: { value: "billing, refund, priority" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save test case/i }));

    await waitFor(() => {
      expect(browserClient.experiments.updateTestCase).toHaveBeenCalledWith("exp_1", "case_1", {
        input_text: "Customer asks for a refund after duplicate billing.",
        expected_output_text: "Acknowledge the duplicate charge and gather account details.",
        notes: "Baseline support case revised.",
        tags: ["billing", "refund", "priority"],
      });
    });

    fireEvent.click(screen.getAllByRole("checkbox", { name: /select test case/i })[1]!);
    await waitFor(() => {
      expect(screen.getByText(/2 selected/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /duplicate test case/i })[0]!);

    await waitFor(() => {
      expect(browserClient.experiments.duplicateTestCase).toHaveBeenCalledWith(
        "exp_1",
        expect.stringMatching(/^case_/),
      );
    });

    const deleteButtons = screen.getAllByRole("button", { name: /delete test case/i });
    fireEvent.click(deleteButtons[1]!);

    await waitFor(() => {
      expect(browserClient.experiments.deleteTestCase).toHaveBeenCalledWith(
        "exp_1",
        expect.stringMatching(/^case_/),
      );
    });
  });

  it("creates, edits, clones, marks baseline, and deletes configs from the detail tab", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.experiments.createConfig.mockResolvedValue({
      id: "cfg_2",
      experiment_id: "exp_1",
      name: "Context answer",
      version_label: "v2",
      description: "Adds context before replying.",
      provider: "anthropic",
      model: "claude-3-5-sonnet",
      workflow_mode: "prompt_plus_context",
      system_prompt: "You are a precise support assistant.",
      user_prompt_template: "Answer with context: {{ input_text }}",
      temperature: 0.4,
      max_output_tokens: 600,
      top_p: null,
      context_bundle_id: null,
      tags: ["context", "thorough"],
      is_baseline: false,
      created_at: "2025-01-05T00:00:00Z",
      updated_at: "2025-01-05T00:00:00Z",
    });
    browserClient.experiments.updateConfig.mockResolvedValue({
      id: "cfg_1",
      experiment_id: "exp_1",
      name: "Direct answer revised",
      version_label: "v1",
      description: "Tighter support reply.",
      provider: "openai",
      model: "gpt-4.1",
      workflow_mode: "single_shot",
      system_prompt: "You are a concise support assistant.",
      user_prompt_template: "Reply clearly to this ticket: {{ input_text }}",
      temperature: 0.1,
      max_output_tokens: 350,
      top_p: 0.8,
      context_bundle_id: null,
      tags: ["cheap", "revised"],
      is_baseline: false,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-06T00:00:00Z",
    });
    browserClient.experiments.cloneConfig.mockResolvedValue({
      id: "cfg_3",
      experiment_id: "exp_1",
      name: "Direct answer revised",
      version_label: "v1-copy",
      description: "Tighter support reply.",
      provider: "openai",
      model: "gpt-4.1",
      workflow_mode: "single_shot",
      system_prompt: "You are a concise support assistant.",
      user_prompt_template: "Reply clearly to this ticket: {{ input_text }}",
      temperature: 0.1,
      max_output_tokens: 350,
      top_p: 0.8,
      context_bundle_id: null,
      tags: ["cheap", "revised"],
      is_baseline: false,
      created_at: "2025-01-07T00:00:00Z",
      updated_at: "2025-01-07T00:00:00Z",
    });
    browserClient.experiments.markConfigBaseline.mockResolvedValue({
      id: "cfg_3",
      experiment_id: "exp_1",
      name: "Direct answer revised",
      version_label: "v1-copy",
      description: "Tighter support reply.",
      provider: "openai",
      model: "gpt-4.1",
      workflow_mode: "single_shot",
      system_prompt: "You are a concise support assistant.",
      user_prompt_template: "Reply clearly to this ticket: {{ input_text }}",
      temperature: 0.1,
      max_output_tokens: 350,
      top_p: 0.8,
      context_bundle_id: null,
      tags: ["cheap", "revised"],
      is_baseline: true,
      created_at: "2025-01-07T00:00:00Z",
      updated_at: "2025-01-08T00:00:00Z",
    });
    browserClient.experiments.deleteConfig.mockResolvedValue(undefined);
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <ExperimentDetailShell
          initialExperiment={{
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support", "triage"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          }}
          initialConfigs={[
            {
              id: "cfg_1",
              experiment_id: "exp_1",
              name: "Direct answer",
              version_label: "v1",
              description: "Fast baseline answer.",
              provider: "openai",
              model: "gpt-4.1-mini",
              workflow_mode: "single_shot",
              system_prompt: "You are a support assistant.",
              user_prompt_template: "Reply to this ticket: {{ input_text }}",
              temperature: 0.2,
              max_output_tokens: 400,
              top_p: 0.9,
              context_bundle_id: null,
              tags: ["cheap", "fast"],
              is_baseline: true,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
          initialTestCases={[]}
        />
      </AppShellProvider>,
    );

    fireEvent.click(screen.getByRole("tab", { name: /configs/i }));

    expect(screen.getByText(/keep editable config variants inside the experiment/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^name$/i), {
      target: { value: "Context answer" },
    });
    fireEvent.change(screen.getByLabelText(/version label/i), {
      target: { value: "v2" },
    });
    fireEvent.change(screen.getByLabelText(/provider/i), {
      target: { value: "anthropic" },
    });
    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "claude-3-5-sonnet" },
    });
    fireEvent.change(screen.getByLabelText(/workflow mode/i), {
      target: { value: "prompt_plus_context" },
    });
    fireEvent.change(screen.getByLabelText(/system prompt/i), {
      target: { value: "You are a precise support assistant." },
    });
    fireEvent.change(screen.getByLabelText(/user prompt template/i), {
      target: { value: "Answer with context: {{ input_text }}" },
    });
    fireEvent.change(screen.getByLabelText(/temperature/i), {
      target: { value: "0.4" },
    });
    fireEvent.change(screen.getByLabelText(/max output tokens/i), {
      target: { value: "600" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "Adds context before replying." },
    });
    fireEvent.change(screen.getByLabelText(/config tags/i), {
      target: { value: "context, thorough" },
    });
    fireEvent.click(screen.getByRole("button", { name: /create config/i }));

    await waitFor(() => {
      expect(browserClient.experiments.createConfig).toHaveBeenCalledWith("exp_1", {
        name: "Context answer",
        version_label: "v2",
        description: "Adds context before replying.",
        provider: "anthropic",
        model: "claude-3-5-sonnet",
        workflow_mode: "prompt_plus_context",
        system_prompt: "You are a precise support assistant.",
        user_prompt_template: "Answer with context: {{ input_text }}",
        temperature: 0.4,
        max_output_tokens: 600,
        top_p: null,
        context_bundle_id: null,
        tags: ["context", "thorough"],
        is_baseline: false,
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Context answer")).toBeInTheDocument();
    });

    const originalConfigCard = screen.getByText("Direct answer").closest("article");
    expect(originalConfigCard).not.toBeNull();

    fireEvent.click(within(originalConfigCard!).getByRole("button", { name: /edit config/i }));
    fireEvent.change(screen.getByLabelText(/model/i), {
      target: { value: "gpt-4.1" },
    });
    fireEvent.change(screen.getByLabelText(/temperature/i), {
      target: { value: "0.1" },
    });
    fireEvent.change(screen.getByLabelText(/max output tokens/i), {
      target: { value: "350" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "Tighter support reply." },
    });
    fireEvent.change(screen.getByLabelText(/config tags/i), {
      target: { value: "cheap, revised" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save config/i }));

    await waitFor(() => {
      expect(browserClient.experiments.updateConfig).toHaveBeenCalledWith("exp_1", "cfg_1", {
        name: "Direct answer",
        version_label: "v1",
        description: "Tighter support reply.",
        provider: "openai",
        model: "gpt-4.1",
        workflow_mode: "single_shot",
        system_prompt: "You are a support assistant.",
        user_prompt_template: "Reply to this ticket: {{ input_text }}",
        temperature: 0.1,
        max_output_tokens: 350,
        top_p: 0.9,
        context_bundle_id: null,
        tags: ["cheap", "revised"],
        is_baseline: true,
      });
    });

    fireEvent.click(within(originalConfigCard!).getByRole("button", { name: /clone config/i }));

    await waitFor(() => {
      expect(browserClient.experiments.cloneConfig).toHaveBeenCalledWith("exp_1", "cfg_1");
    });
    await waitFor(() => {
      expect(screen.getByText("v1-copy")).toBeInTheDocument();
    });

    const clonedConfigCard = screen.getByText("v1-copy").closest("article");
    expect(clonedConfigCard).not.toBeNull();

    fireEvent.click(within(clonedConfigCard!).getByRole("button", { name: /mark baseline/i }));

    await waitFor(() => {
      expect(browserClient.experiments.markConfigBaseline).toHaveBeenCalledWith("exp_1", "cfg_3");
    });

    const createdConfigCard = screen.getByText("Context answer").closest("article");
    expect(createdConfigCard).not.toBeNull();

    fireEvent.click(within(createdConfigCard!).getByRole("button", { name: /delete config/i }));

    await waitFor(() => {
      expect(browserClient.experiments.deleteConfig).toHaveBeenCalledWith("exp_1", "cfg_2");
    });
  });

  it("launches single and multi-config runs from the runs tab", async () => {
    const browserClient = buildBrowserClientMock();
    browserClient.experiments.launchRun.mockResolvedValue({
      id: "run_1",
      experiment_id: "exp_1",
      test_case_id: "case_1",
      config_id: "cfg_1",
      credential_id: "cred_1",
      status: "completed",
      provider: "openai",
      model: "gpt-4.1-mini-2025-04-14",
      workflow_mode: "single_shot",
      config_snapshot: {
        config_id: "cfg_1",
        name: "Concise answer",
        version_label: "v1",
        description: "Primary baseline.",
        provider: "openai",
        model: "gpt-4.1-mini",
        workflow_mode: "single_shot",
        system_prompt_template: "You are a concise support assistant.",
        rendered_system_prompt: "You are a concise support assistant.",
        user_prompt_template: "Reply to this ticket: {{input}}",
        rendered_user_prompt:
          "Reply to this ticket: Customer asks for a refund after duplicate billing.",
        temperature: 0.2,
        max_output_tokens: 350,
        top_p: 0.9,
        context_bundle_id: null,
        tags: ["baseline"],
        is_baseline: true,
      },
      input_snapshot: {
        test_case_id: "case_1",
        input_text: "Customer asks for a refund after duplicate billing.",
        expected_output_text: "Acknowledge the issue and request account details.",
        notes: "Baseline support case.",
        tags: ["billing", "refund"],
      },
      context_snapshot: null,
      output_text: "Refund approved.",
      error_message: null,
      usage_input_tokens: 111,
      usage_output_tokens: 29,
      usage_total_tokens: 140,
      latency_ms: 245,
      estimated_cost_usd: null,
      started_at: "2025-01-05T00:00:00Z",
      finished_at: "2025-01-05T00:00:01Z",
      created_at: "2025-01-05T00:00:00Z",
      updated_at: "2025-01-05T00:00:01Z",
    });
    browserClient.experiments.launchBatchRuns.mockResolvedValue([
      {
        id: "run_2",
        experiment_id: "exp_1",
        test_case_id: "case_1",
        config_id: "cfg_1",
        credential_id: "cred_1",
        status: "completed",
        provider: "openai",
        model: "gpt-4.1-mini",
        workflow_mode: "single_shot",
        config_snapshot: {
          config_id: "cfg_1",
          name: "Concise answer",
          version_label: "v1",
          description: "Primary baseline.",
          provider: "openai",
          model: "gpt-4.1-mini",
          workflow_mode: "single_shot",
          system_prompt_template: "You are a concise support assistant.",
          rendered_system_prompt: "You are a concise support assistant.",
          user_prompt_template: "Reply to this ticket: {{input}}",
          rendered_user_prompt:
            "Reply to this ticket: Customer asks for a refund after duplicate billing.",
          temperature: 0.2,
          max_output_tokens: 350,
          top_p: 0.9,
          context_bundle_id: null,
          tags: ["baseline"],
          is_baseline: true,
        },
        input_snapshot: {
          test_case_id: "case_1",
          input_text: "Customer asks for a refund after duplicate billing.",
          expected_output_text: "Acknowledge the issue and request account details.",
          notes: "Baseline support case.",
          tags: ["billing", "refund"],
        },
        context_snapshot: null,
        output_text: "Refund approved.",
        error_message: null,
        usage_input_tokens: 111,
        usage_output_tokens: 29,
        usage_total_tokens: 140,
        latency_ms: 245,
        estimated_cost_usd: null,
        started_at: "2025-01-05T00:01:00Z",
        finished_at: "2025-01-05T00:01:01Z",
        created_at: "2025-01-05T00:01:00Z",
        updated_at: "2025-01-05T00:01:01Z",
      },
      {
        id: "run_3",
        experiment_id: "exp_1",
        test_case_id: "case_1",
        config_id: "cfg_2",
        credential_id: "cred_2",
        status: "failed",
        provider: "anthropic",
        model: "claude-3-5-sonnet-latest",
        workflow_mode: "single_shot",
        config_snapshot: {
          config_id: "cfg_2",
          name: "Thorough answer",
          version_label: "v2",
          description: "Anthropic variant.",
          provider: "anthropic",
          model: "claude-3-5-sonnet-latest",
          workflow_mode: "single_shot",
          system_prompt_template: "You are a careful support assistant.",
          rendered_system_prompt: "You are a careful support assistant.",
          user_prompt_template: "Review this issue: {{input}}",
          rendered_user_prompt:
            "Review this issue: Customer asks for a refund after duplicate billing.",
          temperature: 0.3,
          max_output_tokens: 500,
          top_p: null,
          context_bundle_id: null,
          tags: ["thorough"],
          is_baseline: false,
        },
        input_snapshot: {
          test_case_id: "case_1",
          input_text: "Customer asks for a refund after duplicate billing.",
          expected_output_text: "Acknowledge the issue and request account details.",
          notes: "Baseline support case.",
          tags: ["billing", "refund"],
        },
        context_snapshot: null,
        output_text: null,
        error_message: "Authentication failed for provider 'anthropic'.",
        usage_input_tokens: null,
        usage_output_tokens: null,
        usage_total_tokens: null,
        latency_ms: null,
        estimated_cost_usd: null,
        started_at: "2025-01-05T00:02:00Z",
        finished_at: "2025-01-05T00:02:01Z",
        created_at: "2025-01-05T00:02:00Z",
        updated_at: "2025-01-05T00:02:01Z",
      },
    ]);
    useApiClientMock.mockReturnValue(browserClient);

    render(
      <AppShellProvider>
        <ExperimentDetailShell
          initialExperiment={{
            id: "exp_1",
            name: "Support triage",
            description: "Compare prompt variants for support tickets.",
            tags: ["support", "triage"],
            is_archived: false,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          }}
          initialConfigs={[
            {
              id: "cfg_1",
              experiment_id: "exp_1",
              name: "Concise answer",
              version_label: "v1",
              description: "Primary baseline.",
              provider: "openai",
              model: "gpt-4.1-mini",
              workflow_mode: "single_shot",
              system_prompt: "You are a concise support assistant.",
              user_prompt_template: "Reply to this ticket: {{input}}",
              temperature: 0.2,
              max_output_tokens: 350,
              top_p: 0.9,
              context_bundle_id: null,
              tags: ["baseline"],
              is_baseline: true,
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
            {
              id: "cfg_2",
              experiment_id: "exp_1",
              name: "Thorough answer",
              version_label: "v2",
              description: "Anthropic variant.",
              provider: "anthropic",
              model: "claude-3-5-sonnet-latest",
              workflow_mode: "single_shot",
              system_prompt: "You are a careful support assistant.",
              user_prompt_template: "Review this issue: {{input}}",
              temperature: 0.3,
              max_output_tokens: 500,
              top_p: null,
              context_bundle_id: null,
              tags: ["thorough"],
              is_baseline: false,
              created_at: "2025-01-03T00:00:00Z",
              updated_at: "2025-01-04T00:00:00Z",
            },
          ]}
          initialTestCases={[
            {
              id: "case_1",
              experiment_id: "exp_1",
              input_text: "Customer asks for a refund after duplicate billing.",
              expected_output_text: "Acknowledge the issue and request account details.",
              notes: "Baseline support case.",
              tags: ["billing", "refund"],
              created_at: "2025-01-01T00:00:00Z",
              updated_at: "2025-01-02T00:00:00Z",
            },
          ]}
        />
      </AppShellProvider>,
    );

    fireEvent.click(screen.getByRole("tab", { name: /runs/i }));

    fireEvent.click(screen.getByRole("radio", { name: /customer asks for a refund/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /concise answer v1/i }));
    fireEvent.click(screen.getByRole("button", { name: /run selected config/i }));

    await waitFor(() => {
      expect(browserClient.experiments.launchRun).toHaveBeenCalledWith("exp_1", {
        test_case_id: "case_1",
        config_id: "cfg_1",
      });
    });
    await waitFor(() => {
      expect(screen.getByText("Refund approved.")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("checkbox", { name: /thorough answer v2/i }));
    fireEvent.click(screen.getByRole("button", { name: /run selected configs/i }));

    await waitFor(() => {
      expect(browserClient.experiments.launchBatchRuns).toHaveBeenCalledWith("exp_1", {
        test_case_id: "case_1",
        config_ids: ["cfg_1", "cfg_2"],
      });
    });
    await waitFor(() => {
      expect(screen.getByText(/authentication failed for provider/i)).toBeInTheDocument();
    });
  });
});
