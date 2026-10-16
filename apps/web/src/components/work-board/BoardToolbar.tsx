import { AssigneeFilterMenu } from "./AssigneeFilterMenu";
import { SearchableSelect } from "./SearchableSelect";
import type { BoardAssignee, BoardIssueType } from "./workBoardApi";

type BoardToolbarProps = {
  search: string;
  onSearchChange: (value: string) => void;
  assignees: BoardAssignee[];
  assigneeFilter: Set<string>;
  onToggleAssignee: (assigneeId: string) => void;
  onClearAssignees: () => void;
  typeFilter: BoardIssueType | "all";
  onTypeFilterChange: (value: BoardIssueType | "all") => void;
};

const TYPE_FILTER_OPTIONS = [
  { value: "all", label: "All types" },
  { value: "user_story", label: "User story" },
  { value: "bug", label: "Bug" }
];

export function BoardToolbar({
  search,
  onSearchChange,
  assignees,
  assigneeFilter,
  onToggleAssignee,
  onClearAssignees,
  typeFilter,
  onTypeFilterChange
}: BoardToolbarProps) {
  return (
    <div className="board-toolbar">
      <label className="board-search">
        <span className="board-search-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="18" height="18">
            <path
              fill="currentColor"
              d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"
            />
          </svg>
        </span>
        <input
          type="search"
          value={search}
          placeholder="Search board"
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>

      <AssigneeFilterMenu
        assignees={assignees}
        assigneeFilter={assigneeFilter}
        onToggleAssignee={onToggleAssignee}
        onClearAssignees={onClearAssignees}
      />

      <div className="board-toolbar-type">
        <SearchableSelect
          label="Type"
          value={typeFilter}
          options={TYPE_FILTER_OPTIONS}
          onChange={(value) => onTypeFilterChange(value as BoardIssueType | "all")}
          placeholder="Filter type…"
        />
      </div>
    </div>
  );
}
