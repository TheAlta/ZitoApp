# Zito

Zito is a FastAPI-based authenticated learning platform with AI-assisted training.

## What it does
- Authenticates learners by phone OTP through sms.ir.
- Stores one canonical user identity with a non-unique `display_name`.
- Keeps long-lived login state in an opaque HttpOnly session cookie.
- Collects seven learner-profile fields incrementally in the chat UI without AI validation.
- Lets the authenticated learner choose a complete published Fake CMS course.
- Serves the pinned course version through a sequential 20-stage learning engine.
- Persists one progress row per stage, blocks stage skipping, and resumes the latest course after login.
- Keeps the Zito avatar visible during course selection and every learning stage.
- Provides typed empty image, video and audio slots ready for future CMS media.
- Shows a display-only coaching checkpoint after each stage; course RAG coaching is scheduled for Sprint 3.
- Shows canonical user identity and profile fields in a separate protected admin UI.
- Soft-deletes users and revokes their active sessions without removing learning history.

## Local URLs
After setup:
- App: `http://127.0.0.1:8000/app/`
- Admin: `http://127.0.0.1:8000/admin` with the admin login page
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Important files
- `DATABASE_V2_DESIGN.md`: canonical database and learning architecture; Sprint 1 schema and Sprint 2 runtime status.
- `PROJECT_RAW_AUDIT.md`: code-derived snapshot of the project before the database V2 migration.
- `SETUP.md`: PostgreSQL, environment, migration and Git setup.
- `src/lib/arvan_client.py`: the only place that calls Arvancloud AIaaS.
- `src/prompts/`: editable system prompts.
- `src/api/routes.py`: authentication, canonical profile, course, 20-stage learning engine and admin routes.

## Security
Do not commit `.env` or real API keys. If an API key was shared in chat or logs, rotate it in the provider dashboard and put the new value only in `.env`.
