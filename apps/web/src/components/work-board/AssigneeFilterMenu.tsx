import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { BOARD_ISSUE_UNASSIGNED, type BoardAssignee } from "./workBoardApi";

function UnassignedAvatar({ size = 28 }: { size?: number }) {
  return (
    <span
      className="board-avatar board-avatar-unassigned"
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" width={size * 0.5} height={size * 0.5} aria-hidden="true">
        <path
          fill="currentColor"
          d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"
        />
      </svg>
    </span>
  );
}

const UNASSIGNED_FILTER: BoardAssignee = {
  assignee_id: BOARD_ISSUE_UNASSIGNED,
  name: "Unassigned",
  initials: "",
  avatar_color: ""
};

function isUnassignedFilter(person: BoardAssignee) {
  return person.assignee_id === BOARD_ISSUE_UNASSIGNED;
}

const VISIBLE_AVATARS = 3;

type AssigneeFilterMenuProps = {
  assignees: BoardAssignee[];
  assigneeFilter: Set<string>;
  onToggleAssignee: (assigneeId: string) => void;
  onClearAssignees: () => void;
};

export function AssigneeFilterMenu({
  assignees,
  assigneeFilter,
  onToggleAssignee,
  onClearAssignees
}: AssigneeFilterMenuProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const moreBtnRef = useRef<HTMLButtonElement>(null);
  const [popoverStyle, setPopoverStyle] = useState<{ top: number; left: number }>({
    top: 0,
    left: 0
  });

  const POPOVER_WIDTH = 280;

  const filterOptions = useMemo(
    () => [...assignees, UNASSIGNED_FILTER],
    [assignees]
  );
  const visible = filterOptions.slice(0, VISIBLE_AVATARS);
  const remaining = filterOptions.slice(VISIBLE_AVATARS);
  const overflow = remaining.length;
  const needle = query.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      remaining.filter((person) => {
        if (person.name.toLowerCase().includes(needle)) return true;
        if (isUnassignedFilter(person)) return false;
        return person.initials.toLowerCase().includes(needle);
      }),
    [remaining, needle]
  );

  useLayoutEffect(() => {
    if (!open || !moreBtnRef.current) return;
    const rect = moreBtnRef.current.getBoundingClientRect();
    const margin = 12;
    let left = rect.right - POPOVER_WIDTH;
    if (left + POPOVER_WIDTH > window.innerWidth - margin) {
      left = window.innerWidth - POPOVER_WIDTH - margin;
    }
    if (left < margin) left = margin;
    setPopoverStyle({ top: rect.bottom + 8, left });
  }, [open]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      const target = event.target as Node;
      if (rootRef.current?.contains(target)) return;
      if (target instanceof Element && target.closest(".board-assignee-popover")) return;
      setOpen(false);
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  return (
    <div className="board-assignee-filter" ref={rootRef} role="group" aria-label="Filter by assignee">
      <button
        type="button"
        className={`board-avatar-filter${assigneeFilter.size === 0 ? " active" : ""}`}
        title="All assignees"
        onClick={onClearAssignees}
      >
        All
      </button>

      {visible.map((person) => {
        const active = assigneeFilter.has(person.assignee_id);
        return (
          <button
            key={person.assignee_id}
            type="button"
            className={`board-avatar-filter circle${active ? " active" : ""}`}
            title={person.name}
            aria-pressed={active}
            onClick={() => onToggleAssignee(person.assignee_id)}
          >
            {isUnassignedFilter(person) ? (
              <UnassignedAvatar />
            ) : (
              <span className="board-avatar" style={{ background: person.avatar_color }}>
                {person.initials}
              </span>
            )}
          </button>
        );
      })}

      {overflow > 0 && (
        <div className="board-assignee-overflow">
          <button
            ref={moreBtnRef}
            type="button"
            className={`board-avatar-filter circle board-avatar-more${open ? " active" : ""}`}
            aria-expanded={open}
            aria-haspopup="listbox"
            title={`${overflow} more assignees`}
            onClick={() => setOpen((current) => !current)}
          >
            <span className="board-avatar board-avatar-more-label">+{overflow}</span>
          </button>
          {open &&
            createPortal(
              <div
                className="board-assignee-popover board-assignee-popover-fixed"
                role="listbox"
                aria-label="More assignees"
                style={{
                  top: popoverStyle.top,
                  left: popoverStyle.left,
                  width: POPOVER_WIDTH
                }}
              >
                <input
                  type="search"
                  className="board-assignee-popover-search"
                  placeholder="Search assignees"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
                <ul className="board-assignee-checklist">
                  {filtered.length === 0 ? (
                    <li className="board-assignee-checklist-empty">No matches</li>
                  ) : (
                    filtered.map((person) => {
                      const checked = assigneeFilter.has(person.assignee_id);
                      return (
                        <li key={person.assignee_id}>
                          <label className="board-assignee-check-row">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => onToggleAssignee(person.assignee_id)}
                            />
                            {isUnassignedFilter(person) ? (
                              <UnassignedAvatar size={26} />
                            ) : (
                              <span
                                className="board-avatar board-avatar-sm"
                                style={{ background: person.avatar_color }}
                                aria-hidden="true"
                              >
                                {person.initials}
                              </span>
                            )}
                            <span className="board-assignee-check-name">{person.name}</span>
                          </label>
                        </li>
                      );
                    })
                  )}
                </ul>
              </div>,
              document.body
            )}
        </div>
      )}
    </div>
  );
}
