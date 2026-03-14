"use client";

import { useAuth } from "@clerk/nextjs";

import { createApiClient } from "@/lib/api/client";

export function useApiClient() {
  const { getToken } = useAuth();

  return createApiClient({
    getToken,
  });
}
