import "server-only";

import { auth } from "@clerk/nextjs/server";

import { createApiClient } from "@/lib/api/client";

export async function getApiClient() {
  const authState = await auth();

  return createApiClient({
    getToken: authState.getToken,
  });
}
