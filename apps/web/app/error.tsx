"use client";

import { ErrorState } from "@/components/states/error-state";

type GlobalErrorPageProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalErrorPage({ error, reset }: GlobalErrorPageProps) {
  return (
    <main className="marketing-page">
      <div className="marketing-shell">
        <div className="state-card">
          <ErrorState
            title="The shell hit an unexpected client-side failure"
            message={error.message || "An unknown UI error interrupted the current route."}
            actionLabel="Try again"
            onAction={reset}
          />
        </div>
      </div>
    </main>
  );
}
