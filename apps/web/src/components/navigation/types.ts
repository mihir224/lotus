export type AppSection = "planner" | "docs" | "calendar" | "chat";

export type NavItem = {
  id: AppSection;
  label: string;
};

export const NAV_ITEMS: NavItem[] = [
  { id: "planner", label: "Planner" },
  { id: "docs", label: "Docs" },
  { id: "calendar", label: "Calendar" },
  { id: "chat", label: "Chat" }
];
