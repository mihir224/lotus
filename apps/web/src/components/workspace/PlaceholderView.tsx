type PlaceholderViewProps = {
  title: string;
  description?: string;
};

export function PlaceholderView({ title, description }: PlaceholderViewProps) {
  return (
    <div className="workspace-placeholder">
      <p className="eyebrow">Coming soon</p>
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </div>
  );
}
