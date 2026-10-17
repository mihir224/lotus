import { useEffect, useState } from "react";
import { authenticatedFetch, authHeaders, type AuthSession } from "../../auth";
import { profileDesignation, type UserProfile } from "./profileUtils";

export function useUserProfile(session: AuthSession | null, authMode: "dev" | "google") {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void authenticatedFetch("/v1/auth/me", { headers: authHeaders() })
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json() as Promise<UserProfile>;
      })
      .then((user) => {
        if (!cancelled) {
          setProfile({ ...user, designation: profileDesignation(user.user_id, user.designation) });
        }
      })
      .catch(() => {
        if (!cancelled && session) {
          setProfile({
            user_id: session.user_id,
            email: session.email,
            name: session.name,
            designation: profileDesignation(session.user_id, session.designation ?? null),
            picture_url: session.picture_url ?? null
          });
        } else if (!cancelled && authMode === "dev") {
          setProfile({
            user_id: "demo-user",
            email: "demo.engineer@lotus.example",
            name: "Demo Engineer",
            designation: "Platform Engineer",
            picture_url: null
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [session, authMode]);

  return { profile, loading };
}
