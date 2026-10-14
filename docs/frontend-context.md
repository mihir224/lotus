# Lotus frontend agent context

## Stack and structure

The frontend is React 19 + TypeScript + Vite in `apps/web/`. `App.tsx` owns the workspace shell and
chat; `CalendarView.tsx` owns calendar, recording, summary, and transcript experiences;
`calendarApi.ts` owns meeting/calendar HTTP calls; `auth.tsx` owns Google Sign-In and bearer headers.

## UI rules

- MUST keep one unified workspace; do not add a mode selector for agent routing.
- MUST preserve the Planner/Specialists/Result visualization as explanatory UI, not user control.
- MUST render evidence provenance and uncertainty returned by the backend.
- MUST fetch calendar and transcript data through `/v1`; never import `demo_data` in the frontend.
- MUST keep Summarize beside View recording and use the backend meeting contract.
- MUST keep layouts functional at the existing desktop and mobile breakpoints.

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
production bundle. Vite proxies `/v1` to `127.0.0.1:8000` in local development.

