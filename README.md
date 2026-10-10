# Zito

Zito is a Persian, RTL learning platform. It combines phone-based learner accounts, AI-authored courses, an administrator CMS, structured learning activities, a version-scoped knowledge base (RAG), an AI Coach, personalized practice, final exams, and certificates.

This README is the main project guide. For the last operational handoff, production status, safe access, and next actions, see [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md). For the current code/database/route audit, see [PROJECT_RAW_AUDIT.md](PROJECT_RAW_AUDIT.md).

## Current Release Status

The production website, API, database, and web/worker services were healthy in the last check (2026-10-06). Production AI is **not launch-ready**: chat and embedding requests to the configured AI Gateway both return `HTTP 403: Account is debtor`. This blocks CMS course generation, AI Coach responses, personalized AI examples, and RAG indexing/retrieval. Do not treat a stage-content fallback as a successful AI response.

The latest local test suite passed: 98 tests. That validates application contracts, not provider billing or live AI availability. Recheck production status before relying on this snapshot.

## Product Flow

1. A learner starts at the public landing page, requests a phone OTP, signs in, and completes a seven-field learning profile.
2. The learner selects a published course and is enrolled in a pinned course version.
3. Courses authored in CMS are divided into a manager-selected number of modules. Each module has a fixed eight-stage learning contract; the stage count is not a course-authoring variable.
4. Stages combine lesson content/summary, flashcards, golden tips and common mistakes, personalized work examples, mini-assessment, and completion/progression behavior.
5. Publishing exposes the course through the public catalog/landing flow and creates approved, module-scoped KB documents and durable indexing jobs.
6. A separate worker creates embeddings. During learning, RAG retrieves only from the learner's current published course/module or explicitly course-global sources. The Coach response should include citations and be grounded in those sources.
7. After modules are completed, the learner may take a versioned final exam and receive a verifiable certificate if they pass.

Legacy flat courses/enrollments remain supported; do not assume all existing learners can be migrated to the module learning engine without checking their pinned versions and progress.

The profile fields cover work/study field, education level, learning goals/interests, AI familiarity, daily learning time, preferred career path, and referral source. Profile answers are persisted to the canonical learner profile and are used where relevant by personalized activities.

## Architecture

- **Application:** FastAPI, Python, SQLAlchemy 2, Pydantic Settings, server-rendered HTML templates with JavaScript/CSS. The frontend is not Angular.
- **Entrypoint:** `src.main:app`; API routes live in `src/api/routes.py`.
- **Database:** PostgreSQL in production; SQLite for lightweight local tests. Alembic migrations are in `migrations/versions/`. PostgreSQL RAG uses pgvector `halfvec` and HNSW.
- **Templates/assets:** `src/templates/` contains app, course overview, admin, login, and certificate pages. `landing/` contains public landing assets/styles.
- **Background indexing:** `src.cli.rag_indexer` is supervised by the `zito-rag-indexer` systemd service. Publishing persists jobs; learner requests do not embed entire course documents.
- **Authentication:** learner phone OTP with an opaque HttpOnly cookie; protected admin session. User soft-delete/block and restore are distinct operations.

Important code locations:

- `src/api/routes.py`: user, admin, learning, CMS, Coach, exam, and certificate API.
- `src/services/cms.py`: course briefs, AI generation, validation, immutable published versions, publishing and KB synchronization.
- `src/services/rag.py`: scoped retrieval, chunking, indexing jobs, worker coordination, status and failure recovery.
- `src/services/coach.py`: grounded Coach replies and retrieval event records.
- `src/services/personalized_stage.py`: learner-profile-aware work examples and source citations.
- `src/services/final_exam.py`: exam lifecycle, grading and certificate issuance.
- `src/lib/arvan_client.py`: OpenAI-compatible chat-completions client.
- `src/lib/arvan_embeddings.py`: OpenAI-compatible embedding client and vector validation.
- `src/prompts/`: prompts for course generation, summaries, assessments, Coach, personalized examples and exams.
- `src/models.py`: SQLAlchemy schema; `src/schemas.py`: API contracts.

## Production Configuration

Never copy credentials into this README, tickets, source code, screenshots, or shell output. Production runtime variables are in the protected server environment; local credentials use the Windows DPAPI vault described in [SECURITY.md](SECURITY.md).

Last checked production values (model names and host only):

- Site: `https://zito.ir`; health endpoint: `https://zito.ir/health`.
- OpenAI-compatible AI base URL: `https://ai.zito.ir/v1`. The application appends `/chat/completions` or `/embeddings`; do not put those suffixes in the configured base URL.
- CMS model: `GPT-4.1`.
- Coach model: `GLM-5.3`.
- Embedding model: `Embedding-3-Large`, 3072 dimensions.
- CMS, Coach, and embeddings currently resolve to the same gateway key unless dedicated variables are configured. The last production audit verified they all resolved to the configured user-provided key. No key value is stored in documentation.
- Production database: PostgreSQL. Local `.env` and production `/opt/zito/app/.env` are private and Git-ignored/not tracked.

Relevant setting aliases are documented in `.env.example` and `src/config.py`: `DATABASE_URL`, `APP_ENV`, `AUTO_CREATE_TABLES`, `ARVAN_API_BASE_URL`, `ARVAN_API_KEY`, `ARVAN_MODEL`, `ARVAN_CONTENT_GENERATION_*`, `ARVAN_EMBEDDING_*`, `ARVAN_MOCK_AI`, `RAG_*`, `ADMIN_*`, `USER_SESSION_DAYS`, `OTP_*`, and `SMSIR_*`.

**Known provider blocker:** The last production probes returned `HTTP 403: Account is debtor` for both chat and embeddings. DNS/SSL and app/database health passed, and the configured key matched the key supplied by the owner. Only the gateway/provider operator can determine whether the debtor status belongs to the gateway account, an upstream provider credential, or the billing tenant associated with that key. Resolve this before live AI acceptance. After resolution, probe chat and embeddings, retry failed jobs for the affected published course, wait for RAG `ready`, and test citations/grounding.

Some older project notes and `.env.example` still mention a direct Arvan endpoint, Bge-m3, and a fixed five-module sample. Those are historical examples, not the last verified production configuration. Keep placeholders only in `.env.example`; reconcile it in a separate configuration cleanup after confirming the provider's supported model IDs and dimensions.

## Local Development

### Quick Mock Run

From PowerShell in the project directory:

```powershell
$env:DATABASE_URL="sqlite:///./local_test.db"
$env:APP_ENV="local"
$env:AUTO_CREATE_TABLES="true"
$env:ARVAN_MOCK_AI="true"
$env:OTP_MOCK="true"
$env:ADMIN_USERNAME="zito_admin"
$env:ADMIN_PASSWORD="local-dev-only-password"
$env:ADMIN_SESSION_SECRET="local-test-session-secret-that-is-long-enough"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

If `.venv` is absent, create it and install pinned dependencies from `requirements.txt` first. Alternatively use the helper in `tools/zito-secrets.ps1` to load protected local settings without printing them.

Open:

- App: `http://127.0.0.1:8000/app/`
- Admin: `http://127.0.0.1:8000/admin` (sign in at `/admin/login`)
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

With `OTP_MOCK=true`, the OTP request response includes a local mock code. Mock AI/SQLite tests do **not** prove real SMS delivery, production AI billing, vector dimensions, live RAG quality, or the production deployment.

### Local PostgreSQL / Real Providers

Follow [SETUP.md](SETUP.md) for PostgreSQL, migrations, optional sms.ir, local vault, RAG worker, and rollback-only verification. Do not point a test or migration at production without explicit scope, backup, and approval. `AUTO_CREATE_TABLES` is for development only; production schema changes go through reviewed Alembic migrations.

## Tests and Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
git diff --check
```

Last verified count: 98 unit/integration tests passed locally. For RAG worker one-shot testing use:

```powershell
.\.venv\Scripts\python.exe -m src.cli.rag_indexer --once --limit 20
```

Use `--watch` only in the supervised systemd service. For real-provider checks, use the safe helper commands in `tools/zito-secrets.ps1` (`verify-rag`, `verify-coach`, `audit-db`) and verify the response is grounded, has citations, and names the expected model. A fallback response is not a pass.

For CMS acceptance, test a disposable draft with different module counts and realistic authoring instructions, wait for generation to finish, review/edit, publish, check landing/catalog, wait for every KB document to index, then test RAG, Coach, personalized examples, progression, final exam and certificate. Use isolated transactions/test users and confirm rollback/cleanup. See [CMS_TEST_CASES.md](CMS_TEST_CASES.md).

## Production Operations

Production host: `185.97.119.60`, SSH user `ubuntu`, app directory `/opt/zito/app`. Credentials are deliberately excluded; request access through the owner using the approved private channel and verify SSH host keys.

Systemd services:

- `zito`: FastAPI application.
- `zito-rag-indexer`: durable KB indexing worker.
- `nginx`: public web/reverse proxy.

Read-only checks:

```bash
sudo systemctl is-active zito zito-rag-indexer nginx
curl --fail --silent --show-error https://zito.ir/health
sudo journalctl -u zito -u zito-rag-indexer --since '1 hour ago' --no-pager
```

Follow [deploy/README.md](deploy/README.md) for worker setup. Deployment procedure: inspect dirty state, confirm exact allowlist and backups, confirm no generation in progress, run tests/compile, transfer only approved files, restart relevant services, verify health and logs, and retain rollback copies. Never deploy the whole dirty worktree or `.env`.

## Security and Access

- `.env`, `.secrets/`, database files, logs and key files are Git-ignored. Check `git status` and `git ls-files` before commits.
- Local secret vault: `.secrets/zito-vault.local.json`, encrypted using Windows DPAPI and tied to the current Windows user/machine. Another agent cannot decrypt it from a different identity; the owner must provision access.
- `tools/zito-secrets.ps1 list` prints secret names only. Do not use commands that dump the vault or `.env`.
- Rotate credentials shared in chat/logs. Update local vault and production runtime safely, verify replacements without printing them, then restart affected services.
- Admin `ADMIN_PASSWORD` seeds the first admin only; existing password hashes live in the database. Do not assume changing the environment variable changes existing admin credentials.

## Repository References

- [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md): production state, access boundaries, deployment history, current blocker and next actions.
- [PROJECT_RAW_AUDIT.md](PROJECT_RAW_AUDIT.md): current code/schema/route and operational audit snapshot.
- [SETUP.md](SETUP.md): environment and local/production-style setup details.
- [SECURITY.md](SECURITY.md): secret handling rules.
- [DATABASE_GUIDE.md](DATABASE_GUIDE.md): current schema guide.
- [DATABASE_V2_DESIGN.md](DATABASE_V2_DESIGN.md): design/migration history; read alongside current models/migrations.
- [CMS_SPRINT_AUDIT.md](CMS_SPRINT_AUDIT.md): CMS progress/known gaps (may have historical formatting; verify code for current behavior).
- [CMS_TEST_CASES.md](CMS_TEST_CASES.md): manual CMS acceptance cases.
- [deploy/README.md](deploy/README.md): RAG worker deployment instructions.

## Current Worktree Warning

The repository currently contains user changes in UI/asset files and backend fixes. Do not `git reset`, checkout, or bulk-deploy the dirty tree. Inspect `git status --short` and each diff first. The latest production backend deployment intentionally excluded UI changes; see `PROJECT_HANDOFF.md` for the file-level list and backup location pattern.
