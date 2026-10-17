# Google authentication and Cloud Run guardrails

Lotus uses Google Identity Services for browser sign-in and verifies every ID token on the
FastAPI server. The Cloud Run service can therefore be publicly reachable so it can serve the
login page, while agent, meeting, and calendar APIs remain protected by the application.

## Create the OAuth client

In Google Cloud Console for `ai-builder-hackthon-vys`:

1. Open **Google Auth Platform** and configure Branding and Audience.
2. Set the app audience to External and publish it to **Production** for the open demo. Lotus only
   uses Sign in with Google/basic identity scopes, which Google exempts from the Testing-mode test
   user restriction, but Production accurately reflects the intended public audience.
3. Under Clients, create a **Web application** OAuth client.
4. Add both local development origins: `http://localhost:5173` and
   `http://127.0.0.1:5173`. Google matches origins exactly.
5. After Cloud Run is deployed, add its exact HTTPS origin as another authorized origin.
6. Copy the client ID. Lotus does not require or store a client secret for this flow.

Configure the root `.env` for local verification:

```dotenv
AUTH_MODE=google
GOOGLE_OAUTH_CLIENT_ID=123456789-example.apps.googleusercontent.com
AGENT_RATE_LIMIT_REQUESTS=10
AGENT_RATE_LIMIT_WINDOW_SECONDS=300
```

Restart `make api`. The Vite frontend obtains the public client ID from `/v1/auth/config`, so no
frontend environment file is needed.

## Protection layers

- Only server-verified Google ID tokens are accepted in Google auth mode.
- Any Google account with a verified email may sign in. Keep the OAuth audience External; publish it
  to Production for the public demo lifecycle.
- `/v1/chat/messages` is limited per authenticated user. The default is 10 requests per 5 minutes.
- Deploy Cloud Run with one maximum instance for the hackathon so the in-memory rate limit is
  consistent and spend is bounded. Use Redis or another shared limiter before scaling beyond one
  instance.
- Set Cloud Run concurrency conservatively and configure billing budgets/alerts.
- Cloud Armor can add edge throttling later, but requires placing Cloud Run behind an external
  Application Load Balancer and is unnecessary for the initial hackathon deployment.

Health, readiness, and `/v1/auth/config` stay public. All knowledge, calendar, meeting, and agent
routes require authentication when `AUTH_MODE=google`.

## Deployment automation boundary

The Google Cloud CLI can automate API enablement, service accounts and IAM, Artifact Registry,
Cloud SQL, Secret Manager, image builds, migration/seed jobs, Cloud Run deployment, scaling limits,
and smoke tests. Creating/configuring the Google Auth Platform branding and Web OAuth client is the
one manual console step in the recommended workflow.

## Cloud Run and Cloud SQL deployment

The deployment script provisions the hackathon Cloud SQL instance, builds one immutable image,
runs the migration and seed jobs, deploys a no-traffic candidate, verifies PostgreSQL readiness,
and then shifts traffic. The API uses live Agent Platform generation with deterministic local
query embeddings and PostgreSQL/pgvector retrieval. It accepts any server-verified Google account,
scales to zero, and caps the service at one instance.

```bash
gcloud auth login
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
./infra/deploy-cloud-run-demo.sh
```

The database password is generated once and stored in Secret Manager as `lotus-db-password`.
Cloud Run receives it through secret injection and reaches PostgreSQL through the attached
`/cloudsql/<instance-connection-name>` Unix socket. Neither the secret nor a resolved database DSN
may appear in source, image layers, deployment output, logs, or traces.

After deployment, add the printed HTTPS origin to the OAuth client's **Authorized JavaScript
origins**, then open the URL and sign in. Do not add a path or trailing slash to the origin.

The current demo service origin is:

```text
https://lotus-6n3idqotvq-el.a.run.app
```
