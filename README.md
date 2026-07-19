# Zito

Zito is a FastAPI-based AI onboarding and training service.

## What it does
- Asks onboarding questions in a chat UI.
- Validates every user answer through Arvancloud AIaaS.
- Stores approved answers in PostgreSQL.
- Moves the user directly into training after onboarding.
- Shows users and answers in a separate protected admin UI.
- Generates training lessons with a simple RAG layer over default accounting, psychology, and law AI knowledge documents.

## Local URLs
After setup:
- Chat: `http://127.0.0.1:8000/chat`
- Admin: `http://127.0.0.1:8000/admin` with the admin login page
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Important files
- `PROJECT_CONTEXT.md`: product and architecture rules for future agent sessions.
- `SETUP.md`: PostgreSQL, environment, migration and Git setup.
- `src/lib/arvan_client.py`: the only place that calls Arvancloud AIaaS.
- `src/prompts/`: editable system prompts.
- `src/api/routes.py`: onboarding, admin and training API routes.

## Security
Do not commit `.env` or real API keys. If an API key was shared in chat or logs, rotate it in the provider dashboard and put the new value only in `.env`.
