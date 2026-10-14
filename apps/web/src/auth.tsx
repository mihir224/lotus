import { useEffect, useRef, useState } from "react";

export interface AuthConfig {
  mode: "dev" | "google";
  google_client_id: string | null;
}

export interface AuthSession {
  credential: string;
  user_id: string;
  email: string | null;
  name: string | null;
}

interface GoogleCredentialResponse {
  credential: string;
}

interface GoogleIdentityApi {
  initialize(options: {
    client_id: string;
    callback: (response: GoogleCredentialResponse) => void;
    ux_mode?: "popup" | "redirect";
  }): void;
  renderButton(
    parent: HTMLElement,
    options: { theme: string; size: string; shape: string; text: string; width: number }
  ): void;
  disableAutoSelect(): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleIdentityApi } };
  }
}

const TOKEN_KEY = "lotus.google.credential";
const USER_KEY = "lotus.google.user";

export function storedAuthSession(): AuthSession | null {
  const credential = sessionStorage.getItem(TOKEN_KEY);
  const rawUser = sessionStorage.getItem(USER_KEY);
  if (!credential || !rawUser) return null;
  try {
    return { credential, ...(JSON.parse(rawUser) as Omit<AuthSession, "credential">) };
  } catch {
    clearAuthSession();
    return null;
  }
}

export function authHeaders(includeJson = false): Record<string, string> {
  const session = storedAuthSession();
  const headers: Record<string, string> = includeJson ? { "Content-Type": "application/json" } : {};
  if (session) headers.Authorization = `Bearer ${session.credential}`;
  else {
    headers["X-Lotus-Tenant"] = "demo";
    headers["X-Lotus-User"] = "demo-user";
  }
  return headers;
}

export function clearAuthSession() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

async function verifyCredential(credential: string): Promise<AuthSession> {
  const response = await fetch("/v1/auth/me", {
    headers: { Authorization: `Bearer ${credential}` }
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Sign-in failed with ${response.status}`);
  }
  const user = (await response.json()) as Omit<AuthSession, "credential">;
  const session = { credential, ...user };
  sessionStorage.setItem(TOKEN_KEY, credential);
  sessionStorage.setItem(USER_KEY, JSON.stringify(user));
  return session;
}

export function signOut() {
  window.google?.accounts.id.disableAutoSelect();
  clearAuthSession();
}

interface GoogleLoginProps {
  clientId: string;
  onAuthenticated: (session: AuthSession) => void;
}

export function GoogleLogin({ clientId, onAuthenticated }: GoogleLoginProps) {
  const button = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const render = () => {
      if (cancelled || !button.current || !window.google) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        ux_mode: "popup",
        callback: async ({ credential }) => {
          setError(null);
          try {
            onAuthenticated(await verifyCredential(credential));
          } catch (reason) {
            clearAuthSession();
            setError(reason instanceof Error ? reason.message : "Google sign-in failed");
          }
        }
      });
      button.current.replaceChildren();
      window.google.accounts.id.renderButton(button.current, {
        theme: "outline",
        size: "large",
        shape: "rectangular",
        text: "signin_with",
        width: 280
      });
    };

    const existing = document.querySelector<HTMLScriptElement>("script[data-lotus-google-signin]");
    if (window.google) render();
    else if (existing) existing.addEventListener("load", render);
    else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.dataset.lotusGoogleSignin = "true";
      script.addEventListener("load", render);
      script.addEventListener("error", () => setError("Unable to load Google Sign-In"));
      document.head.appendChild(script);
    }
    return () => {
      cancelled = true;
      existing?.removeEventListener("load", render);
    };
  }, [clientId, onAuthenticated]);

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="lotus-mark" aria-hidden="true">✦</div>
        <p className="eyebrow">Protected enterprise workspace</p>
        <h1>Sign in to Lotus</h1>
        <p>Use an approved Google account to access agents, meetings, and company knowledge.</p>
        <div className="google-signin" ref={button} />
        {error && <div className="error">{error}</div>}
      </section>
    </main>
  );
}
