# Lotus frontend agent context

## Stack and structure

The frontend is React 19 + TypeScript + Vite in `apps/web/`. `App.tsx` owns the workspace shell,
conversation state, session URL state, theme, and debug preference. `AIWorkspace.tsx` owns the chat
surface; `CalendarView.tsx` owns calendar, recording, summary, and transcript experiences;
`calendarApi.ts` owns meeting/calendar HTTP calls; `auth.tsx` owns Google Sign-In and bearer headers.

## UI rules

- MUST keep one unified workspace; do not add a mode selector for agent routing.
- MUST show the Planner/Specialists/Result inspector only when local Debug Mode is enabled.
- MUST render evidence provenance and uncertainty returned by the backend.
- MUST fetch calendar and transcript data through `/v1`; never import `demo_data` in the frontend.
- MUST keep Summarize beside View recording and use the backend meeting contract.
- MUST preserve server-backed multi-turn chat history and structured in-app navigation targets.
- MUST keep dark as the default theme while retaining the profile light-theme toggle.
- MUST keep layouts functional at the existing desktop and mobile breakpoints.
- MUST render numeric evidence markers only in Debug Mode; navigation actions remain visible.
- MUST keep optimistic user messages visible while a stream is active and ignore stale hydration.

## Chat and session behavior

`?section=agent` starts with a blank conversation. Only
`?section=agent&session=<session-id>` restores a prior conversation. Do not restore a session from
`localStorage`; it makes a URL without a session ID misleading. The `+` header action starts a new
conversation, while the adjacent history action only opens saved history.

Messages append to the ordered conversation instead of replacing the previous run. Accepted sends
clear the composer immediately; Enter sends and Shift+Enter inserts a newline. Markdown is rendered
with the sanitized shared message component. Copy uses the same debug-aware visible content.

## Debug inspector

Debug Mode opens with `Cmd+Option+O` on macOS or `Ctrl+Alt+O` elsewhere. Keyboard detection uses
`event.code === "KeyO"` because Option modifies the produced character. With Debug Mode off, do not
retain run events in browser session history or display the Evidence/Run inspector.

The run inspector counts unique node IDs, merges lifecycle events, and renders separate bounded
Input and Output sections. Tool queries and active filters may be shown, but system prompts,
credentials, hidden reasoning, complete transcripts, and unrestricted payloads must remain hidden.
All inspector surfaces must use semantic theme colors and remain readable in dark mode.

## Authentication flow

The app fetches public `/v1/auth/config` at startup. In `google` mode it renders the official Google
Identity Services button, receives an ID token, and verifies it through `/v1/auth/me` before showing
the workspace. The credential is stored in `sessionStorage` and attached as a Bearer token by
`authHeaders()`.

The client ID is public and comes from the backend. NEVER add an OAuth client secret to frontend
code, Vite variables, HTML, or Git. Backend verification and allowlisting are the security boundary;
frontend state is not authorization.

## API/error behavior

All chat, calendar, and meeting requests MUST use `authHeaders()`. Surface 401, 403, 429, and API
failures to the user and always clear loading state in `finally`. A future shared fetch wrapper may
clear expired sessions on 401; preserve current explicit errors until that is implemented.

## Verification

Run `npm run test --prefix apps/web` for TypeScript and `npm run build --prefix apps/web` for the
production bundle. Vite proxies `/v1` to `127.0.0.1:8000` in local development. Component tests
cover session URL behavior, debug event merging, citation presentation, and dialog interactions.

