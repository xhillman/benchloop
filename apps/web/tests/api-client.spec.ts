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
});
