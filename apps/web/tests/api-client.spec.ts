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
});
