# Zito

Zito is a FastAPI-based authenticated learning platform with AI-assisted training.

## What it does
- Authenticates learners by phone OTP through sms.ir.
- Stores one canonical user identity with a non-unique `display_name`.
- Keeps long-lived login state in an opaque HttpOnly session cookie.
- Collects seven learner-profile fields incrementally in the chat UI without AI validation.
- Enrolls the authenticated learner in a published Fake CMS course.
- Shows users and answers in a separate protected admin UI.
- Soft-deletes users and revokes their active sessions without removing learning history.
- Generates training lessons with a simple RAG layer over default accounting, psychology, and law AI knowledge documents.

## Local URLs
After setup:
- App: `http://127.0.0.1:8000/app/`
- Admin: `http://127.0.0.1:8000/admin` with the admin login page
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Important files
- `DATABASE_V2_DESIGN.md`: canonical database and learning architecture; identity/profile Sprint 1 is implemented by migration `20260728_0006`.
- `PROJECT_RAW_AUDIT.md`: code-derived snapshot of the project before the database V2 migration.
- `SETUP.md`: PostgreSQL, environment, migration and Git setup.
- `src/lib/arvan_client.py`: the only place that calls Arvancloud AIaaS.
- `src/prompts/`: editable system prompts.
- `src/api/routes.py`: authentication, profile, course, admin, legacy onboarding and training routes.

## Security
Do not commit `.env` or real API keys. If an API key was shared in chat or logs, rotate it in the provider dashboard and put the new value only in `.env`.
