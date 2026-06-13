# Pulse Backend

For the zero-cost Render and Supabase production deployment, see
[`CLOUD_DEPLOYMENT.md`](CLOUD_DEPLOYMENT.md).

## Phase 1 setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose -f ..\docker-compose.yml up db -d
alembic upgrade head
python -m app.ingestion.runner
python scripts/check_phase1.py
pytest
```

## Phase 2 enrichment

Set `GROQ_API_KEY` in `.env`, then run a bounded batch:

```powershell
.\.venv\Scripts\python.exe -m app.enrichment.worker --batch-size 20
```

The worker first marks all pending records shorter than 50 characters as
`skipped`. Usable articles are claimed atomically, retried up to three total
attempts, embedded with `all-MiniLM-L6-v2`, and stored as `done`.

Check Phase 2 readiness with:

```powershell
.\.venv\Scripts\python.exe scripts\check_phase2.py
```

## Phase 3 Gmail ingestion

Pulse uses the Gmail API with the read-only scope. It never requests write
access and does not store access tokens.

1. Create a Google Cloud project and enable the Gmail API.
2. Configure the OAuth consent screen and add your Gmail address as a test
   user if the app is in testing mode.
3. Create an OAuth client with application type `Desktop app`.
4. Download its JSON file to `backend/client_secret.json`. This filename is
   ignored by Git.
5. Run the one-time consent flow:

```powershell
.\.venv\Scripts\python.exe scripts\gmail_auth_setup.py `
  --client-secrets client_secret.json --write-env
```

The command verifies the Gmail permission and replaces the refresh token in
`backend/.env`. Add the downloaded client's `client_id` and `client_secret`
values separately:

```env
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
NEWSLETTER_SENDERS=thesequence.substack.com,deeplearning.ai,tldr.tech
```

Do not add the short-lived access token to `.env`. Google refreshes it
automatically from the refresh token.

If Google reports an old `gmail.send` grant, revoke this OAuth app at
`https://myaccount.google.com/permissions` before running the helper again.
Pulse rejects broader grants and accepts only `gmail.readonly`.

Run Gmail ingestion and its live data gate:

```powershell
.\.venv\Scripts\python.exe -m app.ingestion.runner --sources gmail
.\.venv\Scripts\python.exe scripts\check_phase3.py
```

The default pipeline includes Gmail, but a Gmail authentication or network
failure is recorded as a failed Gmail run and does not stop the other sources.

Newsletter extraction removes explicitly labeled sponsor/advertisement
blocks, promotional-only messages, subscription/footer navigation, social
share links, tracking pixels, and hidden preheader content. Same-domain
article posts and members-only source links are retained so the app can show
the cleaned newsletter context while still providing a deep-dive link.

## Phase 4 API and mobile scaffold

Start the complete local stack:

```powershell
cd ..
docker compose up --build -d
```

The API is available at `http://localhost:8000`. `/status` is public; all
other application endpoints require the `X-API-Key` value from
`backend/.env`.

Run the Phase 4 gate:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\check_phase4.py
```

For Expo on a physical phone, set `EXPO_PUBLIC_API_URL` in `mobile/.env` to
this computer's Wi-Fi IPv4 address, not `localhost`. The phone and computer
must be on the same network, and Windows Firewall must allow inbound TCP
traffic on port `8000`.

```powershell
cd mobile
npm install
npx expo start
```

Expo SDK 56 requires Node.js `22.13.0` or newer. `EXPO_PUBLIC_API_WEB_URL`
stays on `http://127.0.0.1:8000` for local browser development.

## Phase 7 quiz and AI digest

Quiz generation and daily digest generation share the persistent Groq quota.
The quiz endpoint stores each generated answer key in PostgreSQL for ten
minutes; submitting the quiz consumes that session and stores the attempt.

```powershell
.\.venv\Scripts\python.exe scripts\check_phase7.py
```

The daily digest scheduler runs at 7:00 AM in `SCHEDULER_TIMEZONE`. It is
idempotent by date and does not create a row when no enriched articles were
ingested in the preceding 24-hour window.

## Phase 8 trends, Ask mode, and notifications

Apply the Phase 8 migration and run its live gate:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts\check_phase8.py
```

The scheduler detects trends nightly at 1:00 AM in `SCHEDULER_TIMEZONE`.
`GET /trends` returns entities found in at least three enriched articles from
the preceding 48 hours. `POST /ask` retrieves up to five relevant article
summaries with pgvector and uses the shared Groq quota only when the retrieval
threshold is met.

Push tokens are stored through `POST /user/push-token`. To enable delivery:

1. Upgrade Node.js to `22.13.0` or newer.
2. Create or link an EAS project for `mobile`:

```powershell
cd ..\mobile
npx eas-cli@latest login
npx eas-cli@latest init
npx eas-cli@latest build:configure
```

3. Set the resulting project ID in `mobile/.env`:

```env
EXPO_PUBLIC_EAS_PROJECT_ID=your-project-uuid
```

4. Configure Android FCM v1 and/or iOS push credentials when EAS prompts.
5. Build and install the included `expo-dev-client` on a physical device:

```powershell
npx eas-cli@latest build --profile development --platform android
```

Use `--platform ios` for an iPhone.
6. Open the installed development build and grant notification permission.

Remote push delivery is not testable in the web build or a simulator. The API
and mobile app work without these credentials; notification registration is
skipped until they are present.
