# Zito Current Project Audit

**Audit date:** 2026-10-07 (Asia/Tehran)
**Workspace:** `C:\Users\ASUS\Desktop\ZitoApp`
**Local HEAD observed:** `df8c4d1`
**Latest Alembic head:** `20260912_0017`
**Status source:** direct repository inspection, local test suite, and production checks performed 2026-10-06. This is a point-in-time report; re-check live systems before operations.

This report replaces the July 2026 pre-V2 snapshot. It intentionally contains no API keys, passwords, database DSN, SMS credentials, private keys, or session cookies. The operator-oriented handoff is [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md); the main setup/product guide is [README.md](README.md).

## 1. Scope and Confidence

Inspected the current FastAPI app, SQLAlchemy models, Alembic history, API routes, CMS/RAG services, prompts, templates, environment aliases, tests and deployment assets. The latest local test run passed all 98 tests.

Production checks confirmed:

- Public `/health` returned `{"status":"ok","database":"ok"}`.
- `zito`, `zito-rag-indexer`, and `nginx` were active.
- The latest user-provided AI gateway key was compared in memory to production configuration and matched the shared/CMS/embedding settings. No key value was printed or saved in this audit.
- Live chat and embeddings both returned `HTTP 403: Account is debtor`. The site and DB being healthy does not imply AI service health.
- No migration was run as part of the latest backend deployment.

The precise billing entity that is debtor is not observable from the application's HTTP response. Arvan/Gateway support must identify whether it is the gateway account, an upstream provider credential, or the tenant attached to the key.

## 2. Repository Map

```text
ZitoApp/
|-- .agents/                  local agent configuration
|-- .github/workflows/        CI configuration
|-- .secrets/                ignored Windows DPAPI vault; never inspect/dump into reports
|-- deploy/systemd/           RAG worker service unit
|-- knowledge_base/           checked-in sample/mock KB sources
|-- landing/                  public landing HTML, styles, scripts and assets
|-- migrations/versions/      Alembic schema history; head 0017
|-- scripts/                  maintenance/audit scripts
|-- src/
|   |-- api/routes.py         FastAPI API and authorization boundary
|   |-- cli/                  worker, seed, audit and verification commands
|   |-- lib/                  gateway clients and shared utilities
|   |-- prompts/              AI prompt templates
|   |-- services/             CMS, RAG, Coach, OTP, learning and exam logic
|   |-- templates/            learner/admin/certificate HTML
|   |-- config.py             environment aliases and production validation
|   |-- db.py                 SQLAlchemy engine/session
|   |-- main.py               app, static mount, startup recovery and page routes
|   |-- models.py             current ORM schema
|   |-- schemas.py            Pydantic API contracts
|   `-- security.py           password/session handling and admin/user guards
|-- tests/                    unittest suite (98 tests at last run)
|-- tools/zito-secrets.ps1    local secret vault helper
|-- .env                      private local settings, ignored
|-- .env.example              placeholder settings; currently has stale model examples
|-- PROJECT_HANDOFF.md        production access, status and next-agent guide
|-- README.md                 main product/development guide
|-- SETUP.md                  detailed local/PostgreSQL/provider setup
|-- SECURITY.md               security and secret handling
|-- DATABASE_GUIDE.md         schema guide
|-- CMS_SPRINT_AUDIT.md        CMS planning/history; validate against code
`-- CMS_TEST_CASES.md          CMS manual acceptance cases
```

Ignored local runtime files such as `.venv/`, `.env`, `.secrets/`, `*.db`, logs, and `.tmp/` are not source artifacts. `.tmp/` currently contains machine-local audit/deployment helpers; they are not a supported release pipeline.

## 3. Application and Architecture

### Runtime and request flow

- Python/FastAPI app: `src.main:app`; templates are rendered as HTML and enhanced by JavaScript/CSS. There is no Angular frontend.
- Root `/` serves `landing/zito.html`; `/app/` serves the learner app; `/app/courses/{course_slug}` serves course overview; `/admin/login` and `/admin` serve admin UI; `/certificate/{certificate_number}` serves certificate verification UI.
- API router is registered from `src/api/routes.py`. FastAPI docs are at `/docs`, OpenAPI at `/openapi.json`, and `/health` checks application/database reachability.
- Production uses PostgreSQL; local quick tests can use SQLite. SQLAlchemy 2 and Alembic are used. PostgreSQL vector support is registered per connection.

### Main domain tables/models

Current ORM models in `src/models.py`:

- Identity/security: `User`, `UserSession`, `UserProfile`, `Admin`, `PhoneOtpCode`.
- Course content: `Course`, `CourseVersion`, `CourseStageContent`, `LearningStageTemplate`, `CourseModule`, `CourseModuleStageContent`.
- Enrollment/progress: `UserCourseEnrollment`, `UserStageProgress`, `UserModuleStageProgress`.
- RAG/Coach: `CourseRagConfig`, `CourseKbDocument`, `CourseKbDocumentChunk`, `CourseKbDocumentModule`, `CourseKbIndexJob`, `CoachThread`, `CoachMessage`, `CoachRetrievalEvent`.
- Assessment: `Exam`, `ExamAttempt`, `Certificate`.

### Course authoring and learning

- A manager enters title/topic/goal/duration/audience/target group/level/module count/learning hours and optional generation instructions.
- CMS generation is in `src/services/cms.py`, prompts in `src/prompts/`. Module count is variable; the learning stage contract is fixed at eight per module.
- The manager reviews/edits brief, module and stage content. A published version is treated as immutable; make a revision to change it.
- **Operational limitation:** generation is currently scheduled through FastAPI `BackgroundTasks`, not a durable generation queue. A long generation can be interrupted by a process restart; startup marks a lingering `generating` version failed. Do not report 202 Accepted as proof generation completed.
- Publish updates catalog/landing-visible course state, creates approved module-scoped KB documents and queues embedding/index jobs.
- Existing learners remain pinned to the course version they enrolled in. Legacy flat course flow remains in code alongside the module flow.

### RAG and AI behavior

- `src/services/rag.py` chunks approved source documents and persists durable `CourseKbIndexJob` records.
- `src/cli/rag_indexer.py` runs finite batches with `--once` or a supervised polling loop with `--watch`.
- PostgreSQL stores 3072-dimensional half-precision vectors and an HNSW index per the current schema contract; retrieval is restricted to the published version/current module plus explicit course-global sources.
- Embeddings call the OpenAI-compatible `/embeddings` endpoint; chat features call `/chat/completions`.
- `src/services/coach.py` returns a Coach answer and retrieval citations. On provider failure, a stage-content fallback may be returned; that is not a successful AI answer.
- `src/services/personalized_stage.py` creates learner-profile-aware examples. Current code only caches successful grounded examples with citations; generic fallback should not be represented as generated AI content.
- `src/services/final_exam.py` owns final-exam lifecycle/grading/certificate issuance; mini quizzes are part of module progression and are separate.

## 4. API Inventory

Use `/docs` as the authoritative request/response contract. These are the principal paths verified in `src/api/routes.py`:

| Area | Methods and paths | Access |
|---|---|---|
| Health | `GET /health` | Public; checks DB too |
| Admin auth | `POST /api/admin/login`, `POST /api/admin/logout`, `GET /api/admin/me` | Login public; me requires admin session |
| Learner auth | `POST /api/auth/otp/request`, `POST /api/auth/otp/verify`, `POST /api/auth/logout` | OTP routes public; verified login issues user session |
| Profile | `GET /api/me`, `GET /api/me/profile`, `PATCH /api/me/profile` | User session |
| Catalog | `GET /api/courses`, `GET /api/courses/slug/{course_slug}` | Public published catalog/overview |
| Enrollment | `POST /api/courses/{course_id}/enroll`, `GET /api/learning/enrollments/current`, `GET /api/learning/enrollments/{enrollment_id}` | User session for enrollment/learner paths |
| Current stage | `GET /api/learning/enrollments/{enrollment_id}/stages/current` | Owning user |
| Coach | `GET/POST /api/learning/enrollments/{enrollment_id}/coach/messages` | Owning user |
| Personalized example | `POST /api/learning/enrollments/{enrollment_id}/stages/{stage_number}/personalized-example` | Owning user; reachable stage only |
| Stage progression | `POST /api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete` | Owning user; progression/assessment rules enforced |
| Final exam | `GET /api/learning/enrollments/{enrollment_id}/final-exam`; `POST .../final-exam/start`; `POST .../final-exam/attempts/{attempt_id}/submit` | Owning user |
| Certificates | `GET /api/learning/enrollments/{enrollment_id}/certificate`, `GET /api/certificates/{certificate_number}` | User route/public verification route |
| Admin user ops | `GET /api/admin/users`, `GET /api/admin/users/{user_id}`, `DELETE /api/admin/users/{user_id}`, `POST .../{user_id}/restore`, `POST .../{user_id}/block`, `POST .../{user_id}/unblock` | Admin session |
| CMS list/create | `GET/POST /api/admin/courses` | Admin session |
| CMS version/revision | `GET /api/admin/courses/{course_id}/versions/{version_number}`, `POST /api/admin/courses/{course_id}/revisions` | Admin session |
| CMS brief/generation | `PATCH .../versions/{version_number}/brief`, `POST .../versions/{version_number}/generate` | Admin session; generation returns 202 and runs in in-process background task |
| CMS content edits | `PATCH .../versions/{version_number}/modules/{module_id}`, `PATCH .../versions/{version_number}/stages/{stage_id}` | Admin session; published version cannot be edited |
| CMS publication | `POST .../versions/{version_number}/publish` | Admin session |
| CMS visibility | `POST .../versions/{version_number}/deactivate`, `/reactivate`, `/soft-delete`, `/restore` | Admin session |
| CMS RAG ops | `GET .../versions/{version_number}/rag-status`, `POST .../versions/{version_number}/rag-retry-failed` | Admin session; retry requires published version |

Admin authentication is a signed admin session cookie; learner authentication uses an opaque HttpOnly session cookie. Do not assume HTTP Basic or expose session cookies. Route code is the authority if paths evolve.

## 5. Environment and Provider Contract

Relevant environment aliases from `src/config.py`:

- Runtime/database: `APP_NAME`, `APP_ENV`, `AUTO_CREATE_TABLES`, `DATABASE_URL`.
- Chat: `ARVAN_API_BASE_URL`, `ARVAN_API_KEY`, `ARVAN_MODEL`, `ARVAN_TIMEOUT_SECONDS`, `ARVAN_MOCK_AI`.
- CMS generation override: `ARVAN_CONTENT_GENERATION_MODEL`, `ARVAN_CONTENT_GENERATION_API_BASE_URL`, `ARVAN_CONTENT_GENERATION_API_KEY`, `ARVAN_CONTENT_GENERATION_TIMEOUT_SECONDS`. Empty base/key reuse shared chat settings.
- Embeddings: `ARVAN_EMBEDDING_API_BASE_URL`, `ARVAN_EMBEDDING_API_KEY`, `ARVAN_EMBEDDING_MODEL`, `ARVAN_EMBEDDING_DIMENSIONS`, `ARVAN_EMBEDDING_TIMEOUT_SECONDS`. Empty base/key reuse shared settings.
- RAG: `RAG_RETRIEVAL_TOP_K`, `RAG_CONTEXT_CHAR_LIMIT`, `RAG_MIN_SIMILARITY`, `RAG_CHUNK_SIZE_CHARS`, `RAG_CHUNK_OVERLAP_CHARS`, `RAG_INDEX_JOB_MAX_ATTEMPTS`, `RAG_INDEX_JOB_LEASE_SECONDS`, `RAG_INDEX_WORKER_POLL_SECONDS`.
- Admin/session: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_SESSION_SECRET`, `ADMIN_SESSION_DAYS`, `USER_SESSION_DAYS`.
- OTP/SMS: `OTP_MOCK`, `OTP_CODE_DIGITS`, `OTP_EXPIRE_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_SECONDS`, `SMSIR_*`, `SMSIR_WELCOME_*`.

Last verified production host/model config (not credentials):

- Base: `https://ai.zito.ir/v1`.
- CMS: `GPT-4.1`; Coach: `GLM-5.3`; embedding: `Embedding-3-Large`, 3072 dimensions.
- All three settings resolved to the same configured key at the last audit; that key matched the latest key supplied by the owner. Actual values intentionally omitted.
- `.env.example` currently contains stale direct-Arvan/Bge-m3 examples and should be reconciled after checking active supported models/dimensions. Do not copy its values into production.

## 6. Production Audit Findings

### Healthy

- Public app health and DB health passed.
- `zito`, `zito-rag-indexer`, and `nginx` were active.
- Production published course structure audit found no structural issues in the four latest inspected versions: course database id 11/version database id 22 (14 modules, 112 stages), course id 10/version id 21 (10/80), course id 7/version id 18 (5/40), and course id 4/version id 13 (5/40). The affected public slug is `course-8`; do not confuse public slug, course database ID, version database ID, and version number. Use slug/version APIs; numeric IDs may change.
- Course-version structure, published exam presence, stage content blocks and mini-quiz duplicate checks were clean in that read-only audit.
- Isolated learner verification transaction rolled back; zero temporary audit users remained.
- No user records were removed by the audit.

### Blocking

- Chat/CMS probe and embedding probe both return `HTTP 403: Account is debtor` from the AI Gateway. A real Coach check falls back to stage content, and a personalized example check returns generic/un-grounded fallback with no model/citations.
- Active course `course-8`, course version database id 22 / version number 1: 14 modules; 171 chunks; only 50 chunks across modules 1, 4, 5, 7 were indexed. Ten jobs failed with the same 403. `CourseRagConfig.status=failed`.
- The error originates at provider/gateway response level. App config matched the supplied key and service networking/SSL passed. Application evidence cannot identify the debtor billing entity; provider support must do so.
- The latest code marks permanent 4xx job errors failed immediately (except transient 408/409/425/429), avoiding pointless retries. This does not solve the external billing condition.
- Do not approve AI/CMS/RAG launch while 403 persists.

### Previously Demonstrated, Not Current Acceptance

- A real CMS generation succeeded in a previous audit before the current debtor response; it took about 112 seconds for a 2-module/16-stage test curriculum. That historical success does not prove current provider health or durability.
- A previous indexed module RAG/Coach test returned grounded citations. A currently unindexed module and the latest live probes fail because the gateway now rejects requests.
- Structural integrity and local unit tests are not substitutes for end-to-end production acceptance.

## 7. Security and Access Boundaries

- `.env`, `.secrets/`, local DB files, logs, private keys/certificates are ignored by Git. Confirm with `git status` and `git ls-files` before changes/releases.
- Local vault path: `.secrets/zito-vault.local.json`; Windows DPAPI ties decryption to this Windows user/machine. A different agent cannot read it without approved access provisioning.
- Helper: `tools/zito-secrets.ps1`; `list` reports only secret names. Keep outputs redacted.
- Production runtime env: `/opt/zito/app/.env`. Production host is `185.97.119.60`, SSH user `ubuntu`. No password/key is recorded in this report; ask the owner to provide access through an approved private channel.
- Rotate any AI key exposed in chat/logs. When rotating, update production and local vault, verify chat and embeddings without printing values, then restart/recheck services.
- Admin password is seeded only for initial administrator creation; changing `ADMIN_PASSWORD` does not replace existing DB password hashes.

## 8. Deployment State and Worktree

- Current local Git `HEAD`: `df8c4d1` (short hash at audit time). Production changes were deployed via targeted file copy, not a release commit/tag.
- Latest deployment included only backend source, no UI and no Alembic migration. Source backups exist under `/opt/zito/backups/backend-fix-*`.
- Initial production backend files: `src/api/routes.py`, `src/lib/arvan_embeddings.py`, `src/services/cms.py`, `src/services/personalized_stage.py`, `src/services/rag.py`. Follow-up changed only `src/services/rag.py` for permanent 4xx handling.
- Dirty local worktree includes pre-existing UI/asset modifications. Do not reset, checkout, or deploy the whole working tree. See `PROJECT_HANDOFF.md` for exact modified file list captured at handoff.
- Before a new production deploy: confirm exact file allowlist, current DB/service state, no generation in progress, backup, tests/compile, then verify services and `/health`; rollback only the deployed files if required.

## 9. Verification and Next Actions

Local tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Worker:

```powershell
.\.venv\Scripts\python.exe -m src.cli.rag_indexer --once --limit 20
```

Next production sequence:

1. Ask Arvan/Gateway support to identify the billing account/provider credential returning debtor, clear the debt or correct the mapped tenant, and confirm chat + embedding model access.
2. Rotate the shared AI key; privately update production/local settings and test minimal chat + embedding calls.
3. Requeue only failed, approved, checksum-current documents for the intended published version. Wait until each module's content is indexed and CMS reports `ready`.
4. Run isolated real CMS generation -> review/edit -> publish -> landing/catalog -> all-module RAG retrieval -> Coach grounded reply/citations -> profile-personalized example/model/citations -> progression -> final exam -> certificate. Confirm no temporary user/draft data persists.
5. Record results and only then sign off launch.

Known documentation drift: `SETUP.md`, `.env.example`, and historical CMS/database notes can still contain old model examples or pre-CMS assumptions. Use current code/config and this dated audit for decisions; update older docs in a scoped follow-up.
