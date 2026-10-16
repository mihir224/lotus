import { CalendarIcon, ChatIcon, ChatsIcon, DocsIcon, PlannerIcon } from "./NavIcons";
import { NAV_ITEMS, type AppSection } from "./types";

type AppRailProps = {
  activeSection: AppSection;
  onSelect: (section: AppSection) => void;
};

const icons: Record<AppSection, typeof PlannerIcon> = {
  "work-board": PlannerIcon,
  docs: DocsIcon,
  calendar: CalendarIcon,
  chats: ChatsIcon,
  agent: ChatIcon
};

export function AppRail({ activeSection, onSelect }: AppRailProps) {
  return (
    <aside className="app-rail" aria-label="Workspace navigation">
      <nav className="app-rail-nav">
        {NAV_ITEMS.map((item) => {
          const Icon = icons[item.id];
          return (
            <button
              type="button"
              key={item.id}
              className={`app-rail-btn${activeSection === item.id ? " active" : ""}`}
              aria-label={item.label}
              aria-current={activeSection === item.id ? "page" : undefined}
              data-tooltip={item.label}
              onClick={() => onSelect(item.id)}
            >
              <Icon className="app-rail-icon" />
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
