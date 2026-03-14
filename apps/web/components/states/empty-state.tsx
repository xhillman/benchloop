import type { ReactNode } from "react";

type EmptyStateProps = {
  label: string;
  title: string;
  description: string;
  action?: ReactNode;
};

export function EmptyState({ label, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="state-badge">{label}</span>
      <h2>{title}</h2>
      <p>{description}</p>
      {action ? <div className="state-action">{action}</div> : null}
    </div>
  );
}
