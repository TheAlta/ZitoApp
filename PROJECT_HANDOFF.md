# Zito Project Handoff

Updated: 2026-10-07 (Asia/Tehran)
Workspace: `C:\Users\ASUS\Desktop\ZitoApp`

This document is the current operational handoff for another engineering agent. It reflects the repository and production checks performed on 2026-10-06/07. Re-check live state before acting; AI Gateway billing was failing at the last check.

## Executive Status

- Zito is a Persian RTL learning platform with an admin CMS, AI-authored courses, module learning flow, course-scoped RAG, AI Coach, personalized examples, final exams, and certificates.
- Production website/API and PostgreSQL health checks passed. Services `zito`, `zito-rag-indexer`, and `nginx` were active.
- Production CMS/Coach/Embedding requests all returned `HTTP 403: Account is debtor` from the configured AI Gateway. This is the current release blocker; do not call AI/RAG healthy or approve launch until the gateway owner/provider clears it and live tests pass.
- Production's configured gateway and all three configured keys were verified to match the latest user-provided endpoint/key. CMS and Coach keys are the same; the embedding key is also the same. No credential values are recorded here.
- Production `course-8`, published version database ID 22 (version number 1), has 14 modules / 112 stages / 171 chunks. Four modules (1, 4, 5, 7; 50 chunks) are indexed; 10 indexing jobs failed due to the gateway 403. RAG config is `failed`.
- The 10 failed jobs were deliberately left failed, not deleted. After gateway recovery, use the CMS RAG retry endpoint or service helper to requeue approved unchanged documents.
- Latest local suite: 98 tests passed. A production health check passed; live AI flow tests failed at the provider boundary with the debtor 403. So production course generation, grounded Coach answers, and personalized AI examples are not currently verified/available.

## Architecture

- **Web/API:** Python 3 + FastAPI, HTML templates with client-side JavaScript/CSS. This is not an Angular app. Entrypoint: `src.main:app`.
- **Persistence:** SQLAlchemy 2, Alembic migrations, PostgreSQL in production. SQLite is used for quick local testing. Production uses `pgvector` `halfvec` embeddings and an HNSW index.
- **Learner identity:** phone OTP, opaque HttpOnly session cookie, canonical `User`, separate `UserProfile`, course enrollment pinned to a course version.
- **Learning:** legacy flat flow remains for older enrollments. Current CMS courses use modules with a fixed 8-stage learning contract per module: summary/content, flashcards, golden tips/common mistakes, personalized work example, mini assessment, and completion-related stages. Module count is controlled by course brief; stage count is fixed at 8.
- **CMS generation:** manager creates a versioned brief (`src/services/cms.py`), AI generates course outline/modules/stages, manager reviews/edits, then publishes. Published versions are immutable; edits should be made in a new revision. Publish exposes the course in public catalog/landing and creates approved KB documents plus durable indexing jobs. Important limitation: the current generation call uses FastAPI `BackgroundTasks`, not a durable generation queue; a process restart can interrupt generation (startup marks an interrupted `generating` version failed). Large generations need monitoring and must not be mistaken for an accepted durable job.
- **RAG:** course content is chunked/indexed asynchronously by `src.cli.rag_indexer` under systemd. Retrieval is scoped to the learner's published course version and current module, with explicit course-global sources allowed. PostgreSQL performs vector retrieval; no embedding of full course content happens inside learner request handlers.
- **AI Coach:** `src/services/coach.py` retrieves course context then requests an answer from the chat gateway; results should be grounded and cited. If the provider fails, Coach can return a stage-content fallback; that is not evidence that AI Coach is healthy.
- **Personalized example:** `src/services/personalized_stage.py`, uses learner profile + course stage/RAG. The current code avoids caching generic/un-grounded fallback results as valid AI examples.
- **Final exam/certificate:** `src/services/final_exam.py`, final exam is separate from per-module mini quizzes; successful grading can issue a verifiable certificate.

### Core modules

- `src/api/routes.py`: auth, learner, learning, Coach, certificate, admin and CMS endpoints.
- `src/services/cms.py`: authoring, generation, validation, versions, publish, CMS-to-KB workflow.
- `src/services/rag.py`: document scope, chunks, durable jobs, worker, retrieval, status and retry logic.
- `src/lib/arvan_client.py`: OpenAI-compatible chat-completions client.
- `src/lib/arvan_embeddings.py`: OpenAI-compatible embeddings client; validates model dimensions and retries transient network/429/5xx conditions.
- `src/services/coach.py`, `src/services/personalized_stage.py`, `src/services/final_exam.py`: learning AI workflows.
- `src/prompts/`: prompt templates; check these before changing authoring or learner quality.
- `src/templates/`: `chat.html`, `course_overview.html`, `admin.html`, login and certificate templates.
- `landing/`: public brand/landing assets and styles.
- `migrations/versions/`: DB history. Current repo head: `20260912_0017_cms_course_authoring.py` (confirm with Alembic before a migration).

## Production Configuration (no secrets)

- Public site: `https://zito.ir`
- AI Gateway base: `https://ai.zito.ir/v1` (OpenAI-compatible paths are appended by the client, e.g. `/chat/completions`, `/embeddings`). Do not append either path to the configured base URL.
- Production host: `185.97.119.60`, SSH user `ubuntu`; application directory `/opt/zito/app`.
- Runtime config is `/opt/zito/app/.env`, owned/protected on server; database is PostgreSQL. Never fetch/print/commit this file or its values.
- Services: `zito` (FastAPI), `zito-rag-indexer` (durable background worker), `nginx`.
- Last verified model IDs: CMS `GPT-4.1`; Coach `GLM-5.3`; embeddings `Embedding-3-Large`, 3072 dimensions. Actual provider account is currently returning 403 debtor for both chat and embeddings.
- Current user-provided gateway key was compared in-memory to each production setting and matched; key material was never printed in the audit. This only proves the configured string matches, not that the provider has enabled/billed the account correctly.
- Relevant env aliases: `DATABASE_URL`, `ARVAN_API_BASE_URL`, `ARVAN_API_KEY`, `ARVAN_MODEL`, `ARVAN_CONTENT_GENERATION_MODEL`, `ARVAN_CONTENT_GENERATION_API_BASE_URL`, `ARVAN_CONTENT_GENERATION_API_KEY`, `ARVAN_EMBEDDING_API_BASE_URL`, `ARVAN_EMBEDDING_API_KEY`, `ARVAN_EMBEDDING_MODEL`, `ARVAN_EMBEDDING_DIMENSIONS`, `ARVAN_EMBEDDING_TIMEOUT_SECONDS`, `ARVAN_MOCK_AI`, `RAG_INDEX_JOB_MAX_ATTEMPTS`, `RAG_INDEX_JOB_LEASE_SECONDS`, `RAG_INDEX_WORKER_POLL_SECONDS`, `OTP_MOCK`, `SMSIR_*`, `ADMIN_*`, `USER_SESSION_DAYS`.
- Effective config falls back: content generation base/key to shared `ARVAN_API_BASE_URL`/`ARVAN_API_KEY`; embedding base/key likewise. Production was verified to use the same current key for CMS, Coach, and embedding.
- `.env.example` and some older README/audit docs still mention the legacy Arvan model endpoint/Bge-m3/five-module example. Do not treat those as current production truth; reconcile docs after service recovery. The live config at audit time was `ai.zito.ir`, `GPT-4.1`, `GLM-5.3`, `Embedding-3-Large`.

## Access and Secret Handling

- Local Windows secret vault: `.secrets/zito-vault.local.json`, Git-ignored and encrypted with Windows DPAPI. It is decryptable only by the same Windows user on the same machine. A different agent/machine needs access provisioned by the user; do not try to bypass DPAPI.
- Secret helper: `tools/zito-secrets.ps1`; `list` displays names only. Typical actions documented in README/SETUP include `verify-coach`, `verify-rag`, `audit-db`, `run-rag-indexer`, `migrate-db`, and `run-server`.
- The local vault includes a server SSH password entry. Do not put it in the report, shell command output, or `.env`. For a new agent, user should provision access through an approved password manager/SSH key. Production user is `ubuntu`; use known-host verification.
- Provider API keys, database DSN/password, admin password/session secret, SMS.ir key/template, and user/admin session cookies are intentionally omitted. Obtain/rotate them through the user/provider console and inject privately. Never ask the user to paste a full key in chat.
- The AI key was previously shared conversationally. Rotate it when practical, update the runtime secret store and local vault, verify chat+embedding with the replacement, then restart services. Rotation itself will invalidate the old key.

## API Surface (selected)

OpenAPI: `https://zito.ir/docs` (or `http://127.0.0.1:8000/docs` locally). `/health` checks app + database.

- Auth: `POST /api/auth/otp/request`, `POST /api/auth/otp/verify`, `POST /api/auth/logout`; `GET /api/me`, `GET/PATCH /api/me/profile`.
- Catalog/enrollment: `GET /api/courses`, `GET /api/courses/slug/{course_slug}`, `POST /api/courses/{course_id}/enroll`.
- Learning: `GET /api/learning/enrollments/current`, `GET /api/learning/enrollments/{id}`, stage/progress endpoints in `src/api/routes.py`.
- Coach: `POST /api/learning/enrollments/{enrollment_id}/coach/messages`; history is `GET` at the same path. Personalized example: `POST /api/learning/enrollments/{enrollment_id}/stages/{stage_number}/personalized-example`.
- Exams/certificates: exam state/start/submit, certificate lookup and public verification endpoints; see OpenAPI and `src/api/routes.py` around lines 1460-1570.
- Admin auth: `POST /api/admin/login`, `POST /api/admin/logout`, `GET /api/admin/me`.
- CMS admin routes all require admin session: `GET/POST /api/admin/courses`; `GET /api/admin/courses/{course_id}/versions/{version_number}`; `POST .../revisions`, `PATCH .../brief`, `POST .../generate` (202 + background task), `PATCH .../modules/{module_id}`, `PATCH .../stages/{stage_id}`, `POST .../publish`, visibility `deactivate/reactivate/soft-delete/restore`, `GET .../rag-status`, `POST .../rag-retry-failed`.
- Admin user management includes list/get/soft-delete/restore/block/unblock routes; check session authorization before use.

## Gateway Failure and Provider Escalation

Observed from production probes on 2026-10-06:

- `POST /chat/completions` for CMS/Coach returns `HTTP 403: Account is debtor`.
- `POST /embeddings` for `Embedding-3-Large` returns the same 403.
- A real Coach request falls back to stage content; Coach event is not a real AI answer. Personalized example returns ungrounded generic fallback with no model/citations. No success should be inferred from the fallback UI.
- Course version 22 structure is intact; the failed job records remain for diagnosis. Jobs 79, 80, 83, 85-91 (10 total) are failed due to provider refusal. Four other jobs succeeded.
- Root cause beyond the exact provider message cannot be distinguished from application-side evidence: Arvan/support must tell whether the debtor status is the gateway account, an upstream model-provider billing credential, or the account/tenant attached to the key. DNS/TLS/app health do not explain this response.
- On support ticket ask them to: (1) identify which billing account/provider credential is debtor, (2) check outstanding balance/invoice and account suspension, (3) confirm the configured API key/tenant can invoke GPT-4.1, GLM-5.3 and Embedding-3-Large, (4) explain reactivation steps and provide a successful test response for both chat-completions and embeddings.
- After support resolves it: test one minimal chat request and one embedding request, then run RAG status and retry failed jobs for the intended published version; wait for every module to be ready; test a retrieved answer with citations and personalized example (model present, grounded, citations present); finally test a disposable draft generation/publish flow in a rollback/isolation harness.

## Deployment History / Safety

- During the latest work, only backend source was copied to production; no migrations and no UI files were deployed as part of that operation.
- Backend files deployed in the first pass: `src/api/routes.py`, `src/lib/arvan_embeddings.py`, `src/services/cms.py`, `src/services/personalized_stage.py`, `src/services/rag.py`.
- A follow-up changed only `src/services/rag.py`: permanent 4xx errors other than transient `408/409/425/429` now fail index jobs immediately instead of retrying unchanged requests. Test added in `tests/test_rag_indexing.py`.
- Both deployments made timestamped source backups under `/opt/zito/backups/backend-fix-*`; use the server backup only for a deliberate rollback, not git reset.
- No migration was run. Local `git HEAD` at handoff is `df8c4d1`; source deployment was a targeted copy, not a commit/tag/release build. Verify hashes/revision before future deployments.
- Before deploy: check status/backup, active course-generation work, exact changed-file allowlist, `py_compile`, local tests. After: check both services, `/health`, public route and logs. Roll back only the deployed backend files if health fails.
- Do not deploy the full dirty worktree. The existing UI and asset changes were intentionally not included in this backend deployment.

## Local Development and Tests

Quick mock setup (see `SETUP.md`):

```powershell
cd C:\Users\ASUS\Desktop\ZitoApp
$env:DATABASE_URL="sqlite:///./local_test.db"
$env:ARVAN_MOCK_AI="true"
$env:OTP_MOCK="true"
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

- App: `http://127.0.0.1:8000/app/`; admin: `/admin`; docs: `/docs`; health: `/health`.
- Run all tests: `.\.venv\Scripts\python.exe -m unittest discover -s tests -q`.
- Latest suite after the permanent-4xx change: 98 passed.
- RAG worker once: `python -m src.cli.rag_indexer --once --limit 20`; supervised mode is `--watch`, used only under systemd.
- Mock AI tests do not prove production AI/provider availability. For end-to-end verification use real provider only in a disposable transaction and inspect grounding/citations.

## Worktree Notes for the Next Agent

Worktree is dirty. Do not reset/checkout or overwrite unrelated changes. At handoff, modified paths included:

- UI/asset changes: `landing/ambient-audio.js`, `landing/zito-ambient.mp3`, `landing/zito-glass.css`, `landing/zito.html`, `src/templates/admin.html`, `src/templates/admin_login.html`, `src/templates/certificate.html`, `src/templates/chat.html`, `src/templates/course_overview.html`, `tests/test_ui_contract.py`. These were pre-existing user work and were not deployed in the backend fix.
- Backend changes: `src/api/routes.py`, `src/lib/arvan_embeddings.py`, `src/services/cms.py`, `src/services/personalized_stage.py`, `src/services/rag.py`.
- Tests: `tests/test_arvan_embeddings.py`, `tests/test_cms_authoring.py`, `tests/test_cms_generation_options.py`, `tests/test_course_flow_v3.py`, `tests/test_rag_indexing.py`.

Temporary audit/deploy scripts are under ignored `.tmp/`; they are machine-local helpers, not a supported release tool. Re-read any file before extending it. Preserve the existing UI work and do not bundle it into deployment unless separately requested.

## Suggested Next Actions

1. User obtains Arvan AI Gateway support response and settles/reactivates the correct gateway/provider billing account. No further DNS/SSL edits are indicated by current evidence.
2. Rotate the API key because it was shared in chat; update production and local private stores, verify both endpoints without printing the key.
3. Requeue only approved failed index jobs for the affected published version; wait until CMS reports RAG `ready` and every scoped module has indexed chunks.
4. Re-run live CMS generation, review/edit, publish, landing/catalog visibility, RAG retrieval, Coach answer+citation, profile-personalized example, final exam and certificate in isolated test data. Verify no test learner or draft records remain.
5. Only after those pass, perform launch sign-off. Keep the stale docs and `.env.example` discrepancies in a separate documentation cleanup task.
