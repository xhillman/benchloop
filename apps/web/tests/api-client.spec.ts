import { describe, expect, it, vi } from "vitest";

import { ApiClientError, createApiClient } from "@/lib/api/client";

describe("api client", () => {
  it("attaches a Clerk bearer token for authenticated requests", async () => {
    const getToken = vi.fn(async () => "session_token");
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return new Response(JSON.stringify({ external_user_id: "user_123" }), {
        status: 200,
        headers: {
          "content-type": "application/json",
        },
      });
    });
    const client = createApiClient({
      fetch: fetchMock,
      getToken,
    });

    const response = await client.auth.getMe();

    expect(response).toEqual({ external_user_id: "user_123" });
    expect(getToken).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/auth/me",
      expect.objectContaining({
        method: "GET",
      }),
    );

    const headers = fetchMock.mock.calls[0]?.[1]?.headers;

    expect(headers).toBeInstanceOf(Headers);
    expect((headers as Headers).get("Authorization")).toBe("Bearer session_token");
  });

  it("skips Clerk auth for public health requests", async () => {
    const getToken = vi.fn(async () => "session_token");
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return new Response(
        JSON.stringify({
          environment: "local",
          service: "benchloop-api",
          status: "ok",
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        },
      );
    });
    const client = createApiClient({
      fetch: fetchMock,
      getToken,
    });

    const response = await client.health.getStatus();

    expect(response).toEqual({
      environment: "local",
      service: "benchloop-api",
      status: "ok",
    });
    expect(getToken).not.toHaveBeenCalled();

    const headers = fetchMock.mock.calls[0]?.[1]?.headers;

    expect(headers).toBeInstanceOf(Headers);
    expect((headers as Headers).get("Authorization")).toBeNull();
  });

  it("normalizes FastAPI error envelopes into ApiClientError", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return new Response(
        JSON.stringify({
          error: {
            code: "authentication_failed",
            details: null,
            message: "Authentication required.",
          },
        }),
        {
          status: 401,
          statusText: "Unauthorized",
          headers: {
            "content-type": "application/json",
          },
        },
      );
    });
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => null,
    });

    const result = client.auth.getMe();

    await expect(result).rejects.toBeInstanceOf(ApiClientError);
    await expect(result).rejects.toMatchObject({
      code: "authentication_failed",
      details: null,
      message: "Authentication required.",
      path: "/api/v1/auth/me",
      status: 401,
    });
  });

  it("routes settings and credential requests through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            default_provider: "openai",
            default_model: "gpt-4.1-mini",
            timezone: "UTC",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "cred_123",
            provider: "anthropic",
            key_label: "Workbench",
            masked_api_key: "••••4321",
            validation_status: "not_validated",
            last_validated_at: null,
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-01T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "cred_123",
            provider: "anthropic",
            key_label: "Workbench",
            masked_api_key: "••••4321",
            validation_status: "valid",
            last_validated_at: "2025-01-02T00:00:00Z",
            created_at: "2025-01-01T00:00:00Z",
            updated_at: "2025-01-02T00:00:00Z",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const settings = await client.settings.update({
      default_provider: "openai",
      default_model: "gpt-4.1-mini",
      timezone: "UTC",
    });
    const createdCredential = await client.settings.createCredential({
      provider: "anthropic",
      api_key: "sk-ant-test-1234",
      key_label: "Workbench",
    });
    const validatedCredential = await client.settings.validateCredential("cred_123");

    expect(settings).toEqual({
      default_provider: "openai",
      default_model: "gpt-4.1-mini",
      timezone: "UTC",
    });
    expect(createdCredential.validation_status).toBe("not_validated");
    expect(validatedCredential.validation_status).toBe("valid");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/settings",
      expect.objectContaining({
        method: "PUT",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/settings/credentials",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/settings/credentials/cred_123/validate",
      expect.objectContaining({
        method: "POST",
      }),
    );

    const updateHeaders = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    const createHeaders = fetchMock.mock.calls[1]?.[1]?.headers as Headers;

    expect(updateHeaders.get("Authorization")).toBe("Bearer session_token");
    expect(createHeaders.get("Content-Type")).toBe("application/json");
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({
        provider: "anthropic",
        api_key: "sk-ant-test-1234",
        key_label: "Workbench",
      }),
    );
  });

  it("routes experiment CRUD and filters through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "exp_2",
            name: "Sales follow-up",
            description: "Warm outbound reply variants.",
            tags: ["sales"],
            is_archived: false,
            created_at: "2025-01-03T00:00:00Z",
            updated_at: "2025-01-03T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(null, {
          status: 204,
        }),
      );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const experiments = await client.experiments.list({
      search: "support",
      tags: ["triage"],
      includeArchived: true,
    });
    const createdExperiment = await client.experiments.create({
      name: "Sales follow-up",
      description: "Warm outbound reply variants.",
      tags: ["sales"],
    });
    await client.experiments.delete("exp_2");

    expect(experiments).toHaveLength(1);
    expect(createdExperiment.name).toBe("Sales follow-up");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/experiments?search=support&tag=triage&include_archived=true",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/experiments",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/experiments/exp_2",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("routes run history filters through the shared client", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          {
            id: "run_1",
            experiment_id: "exp_1",
            experiment_name: "Support triage",
            test_case_id: "case_1",
            config_id: "cfg_1",
            config_name: "Refund baseline",
            config_version_label: "v1",
            test_case_input_preview: "Refund the duplicate charge.",
            status: "completed",
            provider: "openai",
            model: "gpt-4.1-mini",
            workflow_mode: "single_shot",
            tags: ["priority", "refund"],
            latency_ms: 240,
            estimated_cost_usd: 0.0014,
            created_at: "2025-01-10T15:00:00Z",
            started_at: "2025-01-10T15:00:00Z",
            finished_at: "2025-01-10T15:00:02Z",
          },
        ]),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        },
      ),
    );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const runs = await client.runs.list({
      experimentIds: ["exp_1"],
      configIds: ["cfg_1"],
      providers: ["OpenAI"],
      models: ["gpt-4.1-mini"],
      statuses: ["Completed"],
      tags: ["Priority"],
      createdFrom: "2025-01-09T00:00:00Z",
      createdTo: "2025-01-10T23:59:59Z",
      sortBy: "latency_ms",
      sortOrder: "asc",
    });

    expect(runs).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/runs?experiment_id=exp_1&config_id=cfg_1&provider=openai&model=gpt-4.1-mini&status=completed&tag=priority&created_from=2025-01-09T00%3A00%3A00Z&created_to=2025-01-10T23%3A59%3A59Z&sort_by=latency_ms&sort_order=asc",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("routes run detail reads through the shared client", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "run_1",
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
            rendered_user_prompt: "Respond to Customer asks for a refund.",
            temperature: 0.2,
            max_output_tokens: 256,
            top_p: 0.9,
            context_bundle_id: null,
            tags: ["priority"],
            is_baseline: true,
          },
          input_snapshot: {
            test_case_id: "case_1",
            input_text: "Customer asks for a refund.",
            expected_output_text: "Acknowledge the refund.",
            notes: "Core billing case.",
            tags: ["refund"],
          },
          context_snapshot: null,
          output_text: "Refund confirmed.",
          error_message: null,
          usage_input_tokens: 44,
          usage_output_tokens: 12,
          usage_total_tokens: 56,
          latency_ms: 240,
          estimated_cost_usd: 0.0014,
          evaluation: {
            run_id: "run_1",
            overall_score: 4,
            dimension_scores: {
              accuracy: 5,
              clarity: 4,
            },
            thumbs_signal: "up",
            notes: "Strong billing response.",
            created_at: "2025-01-10T15:05:00Z",
            updated_at: "2025-01-10T15:06:00Z",
          },
          started_at: "2025-01-10T15:00:00Z",
          finished_at: "2025-01-10T15:00:02Z",
          created_at: "2025-01-10T15:00:00Z",
          updated_at: "2025-01-10T15:00:02Z",
        }),
        {
          status: 200,
          headers: {
            "content-type": "application/json",
          },
        },
      ),
    );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const run = await client.runs.get("run_1");

    expect(run.experiment_name).toBe("Support triage");
    expect(run.evaluation?.overall_score).toBe(4);
    expect(run.config_snapshot.rendered_user_prompt).toBe("Respond to Customer asks for a refund.");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/runs/run_1",
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

  it("routes rerun requests through the shared client", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "run_2",
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
            name: "Refund baseline",
            version_label: "v1",
            description: "Direct support response.",
            provider: "openai",
            model: "gpt-4.1-mini",
            workflow_mode: "single_shot",
            system_prompt_template: "You are a billing assistant.",
            rendered_system_prompt: "You are a billing assistant.",
            user_prompt_template: "Respond to {{input}}",
            rendered_user_prompt: "Respond to Customer asks for a refund.",
            temperature: 0.2,
            max_output_tokens: 256,
            top_p: 0.9,
            context_bundle_id: null,
            tags: ["priority"],
            is_baseline: true,
          },
          input_snapshot: {
            test_case_id: "case_1",
            input_text: "Customer asks for a refund.",
            expected_output_text: "Acknowledge the refund.",
            notes: "Core billing case.",
            tags: ["refund"],
          },
          context_snapshot: null,
          output_text: "Refund confirmed.",
          error_message: null,
          usage_input_tokens: 44,
          usage_output_tokens: 12,
          usage_total_tokens: 56,
          latency_ms: 240,
          estimated_cost_usd: 0.0014,
          started_at: "2025-01-10T15:00:00Z",
          finished_at: "2025-01-10T15:00:02Z",
          created_at: "2025-01-10T15:00:00Z",
          updated_at: "2025-01-10T15:00:02Z",
        }),
        {
          status: 201,
          headers: {
            "content-type": "application/json",
          },
        },
      ),
    );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const rerun = await client.runs.rerun("run_1");

    expect(rerun.id).toBe("run_2");
    expect(rerun.config_snapshot.rendered_user_prompt).toBe("Respond to Customer asks for a refund.");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/runs/run_1/rerun",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("routes run evaluation updates and deletes through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "run_1",
            overall_score: 5,
            dimension_scores: {
              accuracy: 5,
              clarity: 5,
            },
            thumbs_signal: "up",
            notes: "Most trustworthy response.",
            created_at: "2025-01-10T15:05:00Z",
            updated_at: "2025-01-10T15:06:00Z",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const evaluation = await client.runs.updateEvaluation("run_1", {
      overall_score: 5,
      dimension_scores: {
        accuracy: 5,
        clarity: 5,
      },
      thumbs_signal: "up",
      notes: "Most trustworthy response.",
    });
    await client.runs.deleteEvaluation("run_1");

    expect(evaluation.overall_score).toBe(5);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/runs/run_1/evaluation",
      expect.objectContaining({
        method: "PUT",
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
      JSON.stringify({
        overall_score: 5,
        dimension_scores: {
          accuracy: 5,
          clarity: 5,
        },
        thumbs_signal: "up",
        notes: "Most trustworthy response.",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/runs/run_1/evaluation",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("routes test case CRUD and duplication through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "case_2",
            experiment_id: "exp_1",
            input_text: "Escalate an urgent billing outage report.",
            expected_output_text: null,
            notes: "Fresh case",
            tags: ["billing", "urgent"],
            created_at: "2025-01-03T00:00:00Z",
            updated_at: "2025-01-03T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "case_3",
            experiment_id: "exp_1",
            input_text: "Customer asks for a refund after duplicate billing.",
            expected_output_text: "Acknowledge the issue and request account details.",
            notes: "Baseline support case.",
            tags: ["billing", "refund"],
            created_at: "2025-01-04T00:00:00Z",
            updated_at: "2025-01-04T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(null, {
          status: 204,
        }),
      );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const testCases = await client.experiments.listTestCases("exp_1");
    const createdTestCase = await client.experiments.createTestCase("exp_1", {
      input_text: "Escalate an urgent billing outage report.",
      expected_output_text: null,
      notes: "Fresh case",
      tags: ["billing", "urgent"],
    });
    const duplicatedTestCase = await client.experiments.duplicateTestCase("exp_1", "case_1");
    await client.experiments.deleteTestCase("exp_1", "case_2");

    expect(testCases).toHaveLength(1);
    expect(createdTestCase.id).toBe("case_2");
    expect(duplicatedTestCase.id).toBe("case_3");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/experiments/exp_1/test-cases",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/experiments/exp_1/test-cases",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/experiments/exp_1/test-cases/case_1/duplicate",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/api/v1/experiments/exp_1/test-cases/case_2",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("routes config CRUD, cloning, and baseline actions through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
            created_at: "2025-01-03T00:00:00Z",
            updated_at: "2025-01-03T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "cfg_3",
            experiment_id: "exp_1",
            name: "Direct answer",
            version_label: "v1-copy",
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
            is_baseline: false,
            created_at: "2025-01-04T00:00:00Z",
            updated_at: "2025-01-04T00:00:00Z",
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "cfg_3",
            experiment_id: "exp_1",
            name: "Direct answer",
            version_label: "v1-copy",
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
            created_at: "2025-01-04T00:00:00Z",
            updated_at: "2025-01-05T00:00:00Z",
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(null, {
          status: 204,
        }),
      );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const configs = await client.experiments.listConfigs("exp_1");
    const createdConfig = await client.experiments.createConfig("exp_1", {
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
    const clonedConfig = await client.experiments.cloneConfig("exp_1", "cfg_1");
    const baselineConfig = await client.experiments.markConfigBaseline("exp_1", "cfg_3");
    await client.experiments.deleteConfig("exp_1", "cfg_2");

    expect(configs).toHaveLength(1);
    expect(createdConfig.id).toBe("cfg_2");
    expect(clonedConfig.version_label).toBe("v1-copy");
    expect(baselineConfig.is_baseline).toBe(true);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/experiments/exp_1/configs",
      expect.objectContaining({
        method: "GET",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/experiments/exp_1/configs",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "http://localhost:8000/api/v1/experiments/exp_1/configs/cfg_1/clone",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      "http://localhost:8000/api/v1/experiments/exp_1/configs/cfg_3/baseline",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      5,
      "http://localhost:8000/api/v1/experiments/exp_1/configs/cfg_2",
      expect.objectContaining({
        method: "DELETE",
      }),
    );
  });

  it("routes run launch requests through the shared client", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
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
              name: "Direct answer",
              version_label: "v1",
              description: "Fast baseline answer.",
              provider: "openai",
              model: "gpt-4.1-mini",
              workflow_mode: "single_shot",
              system_prompt_template: "You are a support assistant.",
              rendered_system_prompt: "You are a support assistant.",
              user_prompt_template: "Reply to this ticket: {{input}}",
              rendered_user_prompt:
                "Reply to this ticket: Customer asks for a refund after duplicate billing.",
              temperature: 0.2,
              max_output_tokens: 400,
              top_p: 0.9,
              context_bundle_id: null,
              tags: ["cheap", "fast"],
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
          }),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
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
                name: "Direct answer",
                version_label: "v1",
                description: "Fast baseline answer.",
                provider: "openai",
                model: "gpt-4.1-mini",
                workflow_mode: "single_shot",
                system_prompt_template: "You are a support assistant.",
                rendered_system_prompt: "You are a support assistant.",
                user_prompt_template: "Reply to this ticket: {{input}}",
                rendered_user_prompt:
                  "Reply to this ticket: Customer asks for a refund after duplicate billing.",
                temperature: 0.2,
                max_output_tokens: 400,
                top_p: 0.9,
                context_bundle_id: null,
                tags: ["cheap", "fast"],
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
              started_at: "2025-01-05T00:01:00Z",
              finished_at: "2025-01-05T00:01:01Z",
              created_at: "2025-01-05T00:01:00Z",
              updated_at: "2025-01-05T00:01:01Z",
            },
          ]),
          {
            status: 201,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      );
    const client = createApiClient({
      fetch: fetchMock,
      getToken: async () => "session_token",
    });

    const launchedRun = await client.experiments.launchRun("exp_1", {
      test_case_id: "case_1",
      config_id: "cfg_1",
    });
    const launchedBatch = await client.experiments.launchBatchRuns("exp_1", {
      test_case_id: "case_1",
      config_ids: ["cfg_1", "cfg_2"],
    });

    expect(launchedRun.id).toBe("run_1");
    expect(launchedBatch).toHaveLength(2);
    expect(launchedBatch[1]?.status).toBe("failed");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "http://localhost:8000/api/v1/experiments/exp_1/runs",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://localhost:8000/api/v1/experiments/exp_1/runs/batch",
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.body).toBe(
      JSON.stringify({
        test_case_id: "case_1",
        config_id: "cfg_1",
      }),
    );
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({
        test_case_id: "case_1",
        config_ids: ["cfg_1", "cfg_2"],
      }),
    );
  });
});
