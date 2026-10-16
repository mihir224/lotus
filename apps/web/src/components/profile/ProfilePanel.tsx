import { useEffect, useState } from "react";
import { ProfileAvatar } from "./ProfileAvatar";
import type { UserProfile } from "./profileUtils";

const PANEL_ANIM_MS = 220;

type ProfilePanelProps = {
  open: boolean;
  profile: UserProfile;
  onClose: () => void;
  onSignOut?: () => void;
  showSignOut: boolean;
  theme: "dark" | "light";
  onThemeChange: (theme: "dark" | "light") => void;
};

export function ProfilePanel({
  open,
  profile,
  onClose,
  onSignOut,
  showSignOut,
  theme,
  onThemeChange
}: ProfilePanelProps) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (open) {
      setMounted(true);
      setClosing(false);
      return;
    }
    if (mounted) setClosing(true);
  }, [open, mounted]);

  useEffect(() => {
    if (!closing) return;
    const timer = window.setTimeout(() => {
      setMounted(false);
      setClosing(false);
    }, PANEL_ANIM_MS);
    return () => window.clearTimeout(timer);
  }, [closing]);

  if (!mounted) return null;

  return (
    <>
      <div
        className={`profile-panel-backdrop${closing ? " is-closing" : ""}`}
        role="presentation"
        onClick={onClose}
      />
      <aside
        className={`profile-panel${closing ? " is-closing" : ""}`}
        aria-label="Profile"
        aria-hidden={closing}
      >
        <header className="profile-panel-head">
          <h2>Profile</h2>
          <button type="button" className="board-icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        <div className="profile-panel-body">
          <div className="profile-panel-hero">
            <ProfileAvatar profile={profile} size={72} className="profile-panel-photo" />
            <p className="profile-panel-name">{profile.name ?? "Signed-in user"}</p>
            {profile.designation && (
              <p className="profile-panel-designation">{profile.designation}</p>
            )}
          </div>

          <dl className="profile-panel-fields">
            <div className="profile-panel-field">
              <dt>Email</dt>
              <dd>{profile.email ?? "—"}</dd>
            </div>
            <div className="profile-panel-field">
              <dt>Designation</dt>
              <dd>{profile.designation ?? "—"}</dd>
            </div>
            <div className="profile-panel-field">
              <dt>User ID</dt>
              <dd className="profile-panel-mono">{profile.user_id}</dd>
            </div>
          </dl>
          <label className="setting-row profile-theme-toggle">
            <span><strong>Dark theme</strong><small>Use Lotus in a low-glare dark appearance.</small></span>
            <input type="checkbox" checked={theme === "dark"} onChange={(event) => onThemeChange(event.target.checked ? "dark" : "light")} />
          </label>
        </div>

        {showSignOut && onSignOut && (
          <footer className="profile-panel-foot">
            <button type="button" className="board-secondary-btn profile-signout-btn" onClick={onSignOut}>
              Sign out
            </button>
          </footer>
        )}
      </aside>
    </>
  );
}
