export type MockChatMessage = {
  id: string;
  sender_name: string;
  sender_initials: string;
  is_self: boolean;
  time_label: string;
  body: string;
};

export type MockConversation = {
  id: string;
  section: string;
  /** ISO local datetime; list order is descending (newest first). */
  last_activity_at: string;
  name: string;
  kind: "direct" | "group";
  initials: string;
  avatar_color: string;
  preview: string;
  time_label: string;
  messages: MockChatMessage[];
};

export type MockChatsData = {
  sections: { id: string; label: string }[];
  conversations: MockConversation[];
};

export type LocalChatMessage = MockChatMessage & { local?: boolean };
