type Props = { open: boolean; enabled: boolean; onChange: (enabled: boolean) => void; onClose: () => void };

export function DebugDialog({ open, enabled, onChange, onClose }: Props) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="debug-dialog" role="dialog" aria-modal="true" aria-label="Debug mode" onMouseDown={(event) => event.stopPropagation()}>
        <header><div><p className="eyebrow">Developer tools</p><h2>Debug mode</h2></div><button type="button" className="icon-button" onClick={onClose}>×</button></header>
        <label className="setting-row">
          <span><strong>Show execution details</strong><small>Displays safe evidence, run nodes, timings, and tool counts.</small></span>
          <input type="checkbox" checked={enabled} onChange={(event) => onChange(event.target.checked)} />
        </label>
        <p className="debug-note">Prompts, hidden reasoning, credentials, and full transcripts are never shown.</p>
      </section>
    </div>
  );
}
