import { profileInitials, type UserProfile } from "./profileUtils";

type ProfileAvatarProps = {
  profile: UserProfile;
  size?: number;
  className?: string;
};

export function ProfileAvatar({ profile, size = 40, className = "" }: ProfileAvatarProps) {
  const initials = profileInitials(profile.name, profile.email);
  if (profile.picture_url) {
    return (
      <img
        className={`profile-avatar-img ${className}`.trim()}
        src={profile.picture_url}
        alt=""
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className={`profile-avatar-fallback ${className}`.trim()}
      style={{ width: size, height: size, fontSize: size * 0.34 }}
      aria-hidden="true"
    >
      {initials}
    </span>
  );
}
