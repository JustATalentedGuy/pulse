# Pulse Free Cloud Deployment

This guide deploys the Pulse backend with:

- Render Free Web Service in Singapore
- Supabase Free Postgres, pgvector, Cron, Vault, and Edge Functions
- Expo EAS for an installable Android APK
- A 06:00-22:00 Asia/Kolkata warm window
- Encrypted weekly database backups in private GitHub Actions artifacts

The backend repository is deployed separately from the existing `mobile`
repository. Never commit `.env`, Gmail credentials, database passwords, or
backup passwords.

## 1. Generate Production Secrets

Run this PowerShell snippet twice and retain both values in a password manager:

```powershell
function New-HexSecret {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
  [Convert]::ToHexString($bytes).ToLower()
}

$apiKey = New-HexSecret
$jobSecret = New-HexSecret
$embeddingSecret = New-HexSecret
$backupPassword = New-HexSecret
```

- `apiKey`: Android app access to FastAPI
- `jobSecret`: Supabase Cron access to `/jobs/*`
- `embeddingSecret`: FastAPI access to the embedding Edge Function
- `backupPassword`: encryption key for database backup artifacts

## 2. Create the GitHub Repository

Create a GitHub repository for your fork. Then:

```powershell
cd C:\path\to\pulse
git init -b main
git add .
git commit -m "Prepare free Render and Supabase deployment"
git remote add origin https://github.com/YOUR_USER/pulse.git
git push -u origin main
```

Check the staged files before committing:

```powershell
git status
git ls-files | Select-String -Pattern "\.env|client_secret|quota_state"
```

The second command should return no secret files.

## 3. Create Supabase

1. Create a Supabase Free organization and project.
2. Select Southeast Asia/Singapore.
3. Generate and safely store a strong database password.
4. Open **Project Settings > Database > Connect**.
5. Copy the **Session pooler** URI on port `5432`.

Use the session pooler because it supports IPv4 and persistent application
connections. URL-encode special characters in the password if necessary.

Set it temporarily:

```powershell
$env:SUPABASE_DB_URL = Read-Host "Paste the Supabase session pooler URI"
```

### Deploy the embedding function

Install and authenticate the Supabase CLI:

```powershell
cd C:\path\to\pulse\backend
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase secrets set "EMBEDDING_API_SECRET=$embeddingSecret"
npx supabase functions deploy embed --no-verify-jwt
```

Test it:

```powershell
$embeddingUrl = "https://YOUR_PROJECT_REF.supabase.co/functions/v1/embed"
Invoke-RestMethod `
  -Method Post `
  -Uri $embeddingUrl `
  -Headers @{ "X-Embedding-Secret" = $embeddingSecret } `
  -ContentType "application/json" `
  -Body '{"input":"semantic retrieval for AI engineering"}'
```

The response must report `dimensions: 384` and `model: gte-small`.

## 4. Create the Supabase Schema

First bring the local database to the latest migration:

```powershell
cd C:\path\to\pulse\backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Then apply the same migrations to Supabase without editing `.env`:

```powershell
$env:DATABASE_URL = $env:SUPABASE_DB_URL
$env:DATABASE_SSL = "true"
$env:DATABASE_SSL_MODE = "require"
.\.venv\Scripts\python.exe -m alembic upgrade head
Remove-Item Env:DATABASE_URL
Remove-Item Env:DATABASE_SSL
Remove-Item Env:DATABASE_SSL_MODE
```

## 5. Migrate All Existing Data

The migration copies articles, interactions, bookmarks, preferences, digests,
quiz attempts, trends, settings, and ingestion history. It preserves UUIDs.

```powershell
cd C:\path\to\pulse\backend
$env:SUPABASE_DB_URL = 'YOUR_SESSION_POOLER_URI'
.\.venv\Scripts\python.exe scripts\migrate_local_data.py
```

Verify in Supabase SQL Editor:

```sql
select count(*) as articles from articles;
select enrichment_status, count(*)
from articles
group by enrichment_status
order by enrichment_status;
select count(*) as bookmarks from articles where bookmarked;
select count(*) as quiz_attempts from quiz_attempts;
select pg_size_pretty(pg_database_size(current_database()));
```

The article count should match the local corpus.

## 6. Deploy Render

1. Sign in to Render with GitHub.
2. Select **New > Blueprint**.
3. Connect your `pulse` repository.
4. Render reads the root `render.yaml` and builds from `backend/`.
5. Confirm the service name and Singapore region.
6. Enter every environment value marked `sync: false`.

Use these production-specific values:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Supabase session pooler URI |
| `DATABASE_SSL_MODE` | `require` |
| `GROQ_API_KEY` | Existing Groq key |
| `GMAIL_CLIENT_ID` | Existing value |
| `GMAIL_CLIENT_SECRET` | Existing value |
| `GMAIL_REFRESH_TOKEN` | Existing value |
| `API_KEY` | `$apiKey` |
| `JOB_SECRET` | `$jobSecret` |
| `EMBEDDING_API_URL` | `https://PROJECT_REF.supabase.co/functions/v1/embed` |
| `EMBEDDING_API_SECRET` | `$embeddingSecret` |

Copy the feed, GitHub, and arXiv variables from the local backend `.env`.
Do not set `POSTGRES_USER`, `POSTGRES_PASSWORD`, or `POSTGRES_DB` on Render.

`DATABASE_SSL_MODE=require` keeps the database connection encrypted and avoids
certificate-chain failures in Render's container. For certificate identity
verification, download the Supabase root certificate from **Database Settings
> SSL Configuration**, add it to the image trust store, and change this value
to `verify-full`.

Deploy and wait for:

```text
alembic upgrade head
Uvicorn running
```

Test the public endpoint:

```powershell
$renderUrl = "https://EXACT-HOSTNAME-SHOWN-IN-RENDER.onrender.com"
Invoke-RestMethod "$renderUrl/status"
Invoke-RestMethod `
  -Uri "$renderUrl/feed?limit=10" `
  -Headers @{ "X-API-Key" = $apiKey }
```

Copy the URL from the service header in the Render dashboard. Do not construct
it from the service name: Render may append a suffix when the preferred
hostname is unavailable.

If every route returns plain-text `Not Found`, inspect the response headers:

```powershell
curl.exe -sS -D - "$renderUrl/status" -o -
```

`x-render-routing: no-server` means the hostname is not attached to the
deployed service. Recopy the exact service URL from Render and confirm the
latest deployment has status **Live**. Pulse's `/status` response is JSON.
The API intentionally has no `/` route, so use `/status` for health checks.

## 7. Configure the Warm Window and Jobs

The supplied SQL keeps Render warm every ten minutes from 06:00 through
22:00 IST. It schedules ingestion, Gmail, enrichment, trends, digest,
re-embedding, and retention only inside that window.

Run:

```powershell
cd C:\path\to\pulse\backend
docker run --rm -i `
  -v "${PWD}\supabase:/sql:ro" `
  postgres:17 `
  psql "$env:SUPABASE_DB_URL" `
  -v "api_url=$renderUrl" `
  -v "job_secret=$jobSecret" `
  -f /sql/configure_cloud_cron.sql
```

The script is rerunnable. If an earlier attempt stopped while enabling an
extension, pull the latest repository version and run the same command again.
Supabase's extension is named `supabase_vault`; its SQL objects are exposed
through the `vault` schema.

Verify in Supabase SQL Editor:

```sql
select jobname, schedule, active
from cron.job
where jobname like 'pulse-%'
order by jobname;
```

Expected operating behavior:

- First wake request: 06:00 IST
- Warm heartbeat: every 10 minutes
- Last heartbeat: 22:00 IST
- Render normally sleeps around 22:15 IST
- Overnight app use can still wake Render, with about a one-minute cold start

The heartbeat window consumes about 500 Render instance-hours in a 31-day
month, below the 750-hour free allowance.

## 8. Regenerate Existing Vectors

Old MiniLM vectors are tagged and excluded from cloud semantic search until
they have been regenerated with `gte-small`.

Trigger bounded batches manually:

```powershell
$headers = @{ "X-Job-Secret" = $jobSecret }
do {
  $result = Invoke-RestMethod `
    -Method Post `
    -Uri "$renderUrl/jobs/reembed" `
    -Headers $headers
  $result
} while ($result.remaining -ne 0)
```

Verify:

```sql
select embedding_model, count(*)
from articles
where embedding is not null
group by embedding_model;
```

All embedded records should eventually report `gte-small`.

## 9. Configure Weekly Encrypted Backups

In the GitHub repository settings, add Actions secrets:

- `SUPABASE_DB_URL`: session pooler URI
- `BACKUP_PASSWORD`: `$backupPassword`

Open **Actions > Encrypted Supabase backup > Run workflow** once. Download the
artifact and confirm it contains an `.sql.gz.enc` file.

The public template is manual by default so unconfigured forks do not produce
failed scheduled runs. After the manual backup succeeds, add this trigger to
`.github/workflows/supabase-backup.yml` for weekly Sunday backups:

```yaml
  schedule:
    - cron: "30 2 * * 0"
```

To decrypt:

```powershell
openssl enc -d -aes-256-cbc -pbkdf2 `
  -pass "pass:$backupPassword" `
  -in pulse-YYYY-MM-DD.sql.gz.enc `
  -out pulse.sql.gz
```

Store the backup password outside GitHub. Losing it makes backups unusable.

## 10. Configure the Android Cloud Build

The `cloud` EAS profile produces an installable APK using the production EAS
environment.

```powershell
cd C:\path\to\pulse\mobile
npx eas-cli@latest login
npx eas-cli@latest init

npx eas-cli@latest env:create --name EXPO_PUBLIC_API_URL `
  --value $renderUrl --environment production --visibility plaintext
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_AUTO_HOST `
  --value false --environment production --visibility plaintext
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_PORT `
  --value 443 --environment production --visibility plaintext
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_TIMEOUT_MS `
  --value 75000 --environment production --visibility plaintext
npx eas-cli@latest env:create --name EXPO_PUBLIC_API_KEY `
  --value $apiKey --environment production --visibility sensitive
npx eas-cli@latest env:create --name EXPO_PUBLIC_EAS_PROJECT_ID `
  --value YOUR_EAS_PROJECT_ID `
  --environment production --visibility plaintext
npx eas-cli@latest env:create `
  --name EXPO_PUBLIC_PUSH_NOTIFICATIONS_ENABLED `
  --value false --environment production --visibility plaintext

npx eas-cli@latest build --profile cloud --platform android
```

Download and install the generated APK. The API key is bundled in the APK and
must be treated as a gate for a private personal app, not as strong user
authentication. Do not distribute the APK publicly.

## 11. Final Verification

Run these checks from the installed Android app:

1. Feed loads while the local computer and Docker are off.
2. Search works in Exact, Semantic, and Hybrid modes.
3. Bookmark and read state survive app and backend restarts.
4. Quiz generation and submission survive a Render restart within ten minutes.
5. Ask mode returns grounded citations.
6. Digest and trends update after their morning jobs.
7. At 06:05 IST, `/status` shows a recent ingestion.

Monitor storage monthly:

```sql
select pg_size_pretty(pg_database_size(current_database()));
```

Supabase Free becomes read-only above 500 MB. The weekly retention job deletes
articles older than 180 days, skipped records older than 30 days, old ingestion
runs, expired quiz sessions, and enriched raw HTML.

## Rollback

The local Docker stack remains supported:

```powershell
cd C:\path\to\pulse
docker compose up --build -d
```

Local Docker uses `Dockerfile.local`, the local MiniLM model, the file quota,
and APScheduler. Cloud uses the slim `Dockerfile`, Supabase embeddings,
database quota state, and Supabase Cron.
