import Link from "next/link";
import type { ReactNode } from "react";

type AuthScreenProps = {
  eyebrow: string;
  title: string;
  description: string;
  alternateHref: string;
  alternateLabel: string;
  children: ReactNode;
};

export function AuthScreen({
  eyebrow,
  title,
  description,
  alternateHref,
  alternateLabel,
  children,
}: AuthScreenProps) {
  return (
    <main className="auth-page">
      <div className="auth-panel">
        <section className="auth-copy">
          <span className="brand-mark">Benchloop</span>
          <p className="eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{description}</p>
          <div className="cta-row">
            <Link className="cta-link secondary" href={alternateHref}>
              {alternateLabel}
            </Link>
            <Link className="cta-link secondary" href="/">
              Back to landing page
            </Link>
          </div>
        </section>

        <section className="auth-form">{children}</section>
      </div>
    </main>
  );
}
