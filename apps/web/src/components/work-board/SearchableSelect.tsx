import { useEffect, useId, useRef, useState } from "react";

export type SearchableSelectOption = {
  value: string;
  label: string;
};

type SearchableSelectProps = {
  label: string;
  value: string;
  options: SearchableSelectOption[];
  onChange: (value: string) => void;
  placeholder?: string;
};

export function SearchableSelect({
  label,
  value,
  options,
  onChange,
  placeholder = "Search…"
}: SearchableSelectProps) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = options.find((option) => option.value === value);
  const needle = query.trim().toLowerCase();
  const filtered = options.filter(
    (option) =>
      option.label.toLowerCase().includes(needle) ||
      option.value.toLowerCase().includes(needle)
  );

  useEffect(() => {
    if (!open) setQuery(selected?.label ?? "");
  }, [open, selected]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  function pick(next: string) {
    onChange(next);
    setOpen(false);
  }

  return (
    <div className="board-field searchable-select" ref={rootRef}>
      <span>{label}</span>
      <div className={`searchable-select-control${open ? " open" : ""}`}>
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          value={open ? query : (selected?.label ?? "")}
          placeholder={placeholder}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setOpen(true);
            setQuery(selected?.label ?? "");
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              event.currentTarget.blur();
            }
            if (event.key === "Enter" && open && filtered[0]) {
              event.preventDefault();
              pick(filtered[0].value);
            }
          }}
        />
        <span className="searchable-select-chevron" aria-hidden="true">
          ▾
        </span>
        {open && (
          <ul id={listId} className="searchable-select-list" role="listbox">
            {filtered.length === 0 ? (
              <li className="searchable-select-empty">No matches</li>
            ) : (
              filtered.map((option) => (
                <li key={option.value} role="option" aria-selected={option.value === value}>
                  <button
                    type="button"
                    className={option.value === value ? "active" : ""}
                    onClick={() => pick(option.value)}
                  >
                    {option.label}
                  </button>
                </li>
              ))
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
