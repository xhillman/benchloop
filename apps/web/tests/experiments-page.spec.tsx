import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      create: vi.fn(),
      createTestCase: vi.fn(),
      delete: vi.fn(),
      deleteTestCase: vi.fn(),
      duplicateTestCase: vi.fn(),
      get: vi.fn(),
      list: vi.fn(),
      listTestCases: vi.fn(),
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
});
