type ErrorStateProps = {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function ErrorState({ title, message, actionLabel, onAction }: ErrorStateProps) {
  return (
    <div className="error-state">
      <span className="state-badge">Error state</span>
      <h2>{title}</h2>
      <p>{message}</p>
      {actionLabel && onAction ? (
        <div className="state-action">
          <button onClick={onAction} type="button">
            {actionLabel}
          </button>
        </div>
      ) : null}
    </div>
  );
}
