export type AppSection = "work-board" | "docs" | "calendar" | "chat";

export type NavItem = {
  id: AppSection;
  label: string;
};

export const NAV_ITEMS: NavItem[] = [
  { id: "work-board", label: "Work Board" },
  { id: "docs", label: "Docs" },
  { id: "calendar", label: "Calendar" },
  { id: "chat", label: "Chat" }
];
