import type { FormEvent, KeyboardEvent } from "react";

export function ChatComposer({
  value,
  loading,
  onChange,
  onSubmit,
  onCancel
}: {
  value: string;
  loading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onCancel: () => void;
}) {
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit();
  }
  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }
  return (
    <form className="composer" onSubmit={submit}>
      <textarea
        aria-label="Ask Iris"
        placeholder="Ask about projects, documents, meetings, research, or code…"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKeyDown}
        rows={3}
      />
      <div>
        <span>Enter to send · Shift+Enter for a new line</span>
        {loading ? (
          <button type="button" onClick={onCancel}>Cancel</button>
        ) : (
          <button type="submit" disabled={!value.trim()}>Ask Iris</button>
        )}
      </div>
    </form>
  );
}
