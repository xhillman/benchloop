type LoadingStateProps = {
  label: string;
  title: string;
  description: string;
};

export function LoadingState({ label, title, description }: LoadingStateProps) {
  return (
    <div className="loading-state">
      <span className="state-badge">{label}</span>
      <h2>{title}</h2>
      <p>{description}</p>
    </div>
  );
}
