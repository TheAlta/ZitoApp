# Zito Setup

## Fast Local Test Without PostgreSQL
Use this path first. It runs the app with a local SQLite file and mock AI.

```powershell
cd C:\Users\ASUS\Desktop\ZitoApp
$env:DATABASE_URL="sqlite:///./local_test.db"
$env:AUTO_CREATE_TABLES="false"
$env:ARVAN_MOCK_AI="true"
$env:ADMIN_USERNAME="zito_admin"
$env:ADMIN_PASSWORD="local-dev-only-password"
$env:ADMIN_SESSION_SECRET="local-test-session-secret-that-is-long-enough"
$env:USER_SESSION_DAYS="3650"
$env:OTP_MOCK="true"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

Open in browser:
- User app: `http://127.0.0.1:8000/app/`
- Admin panel: `http://127.0.0.1:8000/admin`
- API docs: `http://127.0.0.1:8000/docs`

OTP mock API test:
- Request code: `POST /api/auth/otp/request`
- Verify code: `POST /api/auth/otp/verify`
- When `OTP_MOCK=true`, the request response includes `mock_code` for local testing.

Admin login for local test:
- username: `zito_admin`
- password: `local-dev-only-password`

## What To Test In The Browser
1. Open `/`.
2. Click `شروع کنید`.
3. Enter any preferred name and a phone number.
4. If `OTP_MOCK=true`, the modal shows the local test code. If `OTP_MOCK=false`, read the SMS code.
5. Enter the OTP code and submit.
6. `/app/` opens, greets you by first name, and asks the profile questions in chat.
7. Answer all seven profile questions. Every accepted chat answer is saved immediately in `user_profiles` without AI validation.
8. After the last answer, Zito enrolls the user in the current published Fake CMS course and shows the learning planet.
9. Open `/admin/login`; after login, you should see saved users.

The seven canonical profile fields are:

- work or study field
- education level
- learning goals and interests
- AI familiarity
- daily learning minutes
- preferred career path
- referral source

## Real Arvan Mode
Create `.env` from `.env.example` and set:

```env
DATABASE_URL=sqlite:///./local_test.db
AUTO_CREATE_TABLES=false
ARVAN_MOCK_AI=false
ARVAN_API_BASE_URL=https://arvancloudai.ir/gateway/models/GPT-5.4-Mini/YOUR_ENDPOINT_TOKEN/v1
ARVAN_API_KEY=your_real_key
ARVAN_MODEL=GPT-5.4-Mini
ADMIN_USERNAME=zito_admin
ADMIN_PASSWORD=choose_a_strong_password
ADMIN_SESSION_SECRET=choose_a_long_random_session_secret
USER_SESSION_DAYS=3650
OTP_MOCK=true
```

Important: do not commit `.env`. If an API key was shared in chat, rotate it in Arvan and use a new one.
SSH/server passwords do not belong in `.env`; keep them in your password manager or replace password login with SSH keys.

## Real sms.ir OTP Mode
Keep local development on `OTP_MOCK=true`. To enable real SMS, get these values from the sms.ir panel and set them only in private `.env` files:

```env
OTP_MOCK=false
SMSIR_API_URL=https://api.sms.ir/v1
SMSIR_API_KEY=your_smsir_api_key
SMSIR_TEMPLATE_ID=your_smsir_template_id
SMSIR_CODE_PARAMETER=Code
SMSIR_TIMEOUT_SECONDS=10
```

The SMS template should contain the same parameter name, for example `Code`.

## PostgreSQL Production Setup
PostgreSQL is not required for quick local testing. For production or a serious dev database:

```sql
CREATE DATABASE zito_app;
CREATE USER zito_app WITH ENCRYPTED PASSWORD 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE zito_app TO zito_app;
\c zito_app
GRANT ALL ON SCHEMA public TO zito_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO zito_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO zito_app;
```

Then set:

```env
DATABASE_URL=postgresql+psycopg://zito_app:CHANGE_ME_STRONG_PASSWORD@localhost:5432/zito_app
AUTO_CREATE_TABLES=false
```

Run migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

When using the private local vault, the equivalent command loads `DATABASE_URL` without printing it:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 migrate-db
```

## Syncing the Mock Knowledge Base

The checked-in Markdown source at `knowledge_base/personal-development-ai-mock-kb.md` is the approved mock source for the five-module sample course. Syncing it updates only the course KB documents, their module scopes, chunks, and durable indexing jobs; it does not call Arvan.

Preview a sync without changing PostgreSQL:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 sync-mock-kb -DryRun
```

Apply the source to PostgreSQL, then process the queued jobs separately:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 sync-mock-kb
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 run-rag-indexer -Limit 20
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 verify-rag
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 audit-db
```

Each imported document stores a `source_reference`, such as `knowledge_base/personal-development-ai-mock-kb.md#module-2`, so future CMS content can replace this mock workflow without changing the learner-facing retrieval path.
`verify-rag` sends one sample question through the configured embedding endpoint and prints only retrieval metadata: source title, module/course scope, and similarity score.
Use `verify-rag -ModuleNumber 2` to inspect another module without exposing the underlying source text.

## Verifying The Grounded Course Coach

After RAG retrieval is healthy, run one end-to-end Coach check with the private vault:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 verify-coach
```

`verify-coach` sends a course-relevant question through embeddings, local pgvector retrieval and the configured Arvan chat model. It creates a temporary learner only inside the current transaction and rolls it back before exit. The command prints metadata only, never API keys, profile data or KB text. Use `verify-coach -ModuleNumber 2` to verify a different course module.

## RAG Indexing Worker

Course KB documents are chunked and indexed by a separate worker. Learner
requests never create embeddings for course content. After an approved KB
document is added or changed, run one local batch with the private vault:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 run-rag-indexer -Limit 20
```

The result contains only counts such as `processed`, `succeeded`, `retry`, and
`failed`; it never prints API keys or source text. A `retry` result means the
same durable job will be attempted later. The reviewed production unit template
is [deploy/systemd/zito-rag-indexer.service](deploy/systemd/zito-rag-indexer.service);
follow [deploy/README.md](deploy/README.md) during an approved deployment.

## Database Safety Audit

Run the aggregate-only audit before a migration or any future cleanup of the
legacy flat learning engine:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 audit-db
```

It reports only counts: current Alembic revision, flat-vs-module learning
usage, enrollment course/version mismatches, invalid progress values, and RAG
job statuses. It never prints phone numbers, learner profile data, secrets or
KB text.

## Stop The Server
In the PowerShell window where Uvicorn is running, press:

```text
Ctrl + C
```
