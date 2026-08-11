# Zito

Zito is a FastAPI-based authenticated learning platform with AI-assisted training.

## What it does
- Authenticates learners by phone OTP through sms.ir.
- Stores one canonical user identity with a non-unique `display_name`.
- Keeps long-lived login state in an opaque HttpOnly session cookie.
- Collects seven learner-profile fields incrementally in the chat UI without AI validation.
- Lets the authenticated learner choose a complete published Fake CMS course.
- Keeps legacy version 1 enrollments on the original flat 20-stage engine while new enrollments use the module-scoped engine.
- Serves the active Fake CMS course as five ordered course modules, each with the same 20 reusable educational templates (100 stored learning items in the sample version).
- Persists one canonical module-stage progress row per item for version 2, blocks skipping, and resumes the latest course after login.
- Keeps the Zito avatar visible during course selection and every learning stage.
- Provides typed empty image, video and audio slots ready for future CMS media, plus course-version and module scopes for future RAG retrieval.
- Shows a display-only coaching checkpoint after each stage; course RAG coaching is scheduled for Sprint 3.
- Shows canonical user identity and profile fields in a separate protected admin UI.
- Soft-deletes users and revokes their active sessions without removing learning history; a later verified phone OTP restores the same account. Blocking is a separate admin operation.

## Local URLs
After setup:
- App: `http://127.0.0.1:8000/app/`
- Admin: `http://127.0.0.1:8000/admin` with the admin login page
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Important files
- `DATABASE_V2_DESIGN.md`: implemented Sprint 1/Sprint 2.5 schema status plus the remaining future database target.
- `PROJECT_RAW_AUDIT.md`: code-derived snapshot of the project before the database V2 migration.
- `SETUP.md`: PostgreSQL, environment, migration and Git setup.
- `src/lib/arvan_client.py`: the only place that calls Arvancloud AIaaS.
- `src/prompts/`: editable system prompts.
- `src/api/routes.py`: authentication, canonical profile, course, legacy flat and module-scoped learning engines, and admin routes.

## Security
Do not commit `.env` or real API keys. If an API key was shared in chat or logs, rotate it in the provider dashboard.

## Local secret vault
Use the Windows-only DPAPI vault instead of manually editing local `.env` files or pasting keys into chat. The encrypted local file is `.secrets/zito-vault.local.json`, which is ignored by Git and can be decrypted only by the same Windows user on the same machine.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 set env.ARVAN_EMBEDDING_API_BASE_URL
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 set env.ARVAN_EMBEDDING_API_KEY
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 list
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 run-server -Port 8000 -Reload
```

The `set` prompt masks the pasted value. `list` prints only secret names, never values. Production keeps a separate protected runtime environment on the server; it is never committed to Git.
