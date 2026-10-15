export type UserProfile = {
  user_id: string;
  email: string | null;
  name: string | null;
  designation: string | null;
  picture_url: string | null;
};

export function profileInitials(name: string | null, email: string | null): string {
  const source = name?.trim() || email?.split("@")[0] || "User";
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[parts.length - 1][0] ?? ""}`.toUpperCase();
  }
  return source.slice(0, 2).toUpperCase();
}
