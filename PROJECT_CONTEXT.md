# Zito Project Context

## Product Goal
Zito is an AI onboarding and training service. The user talks to Zito, answers a small set of profile questions, and each answer is validated by Arvancloud AIaaS. After the profile is complete, the user does not stop at "sent to admin"; the chat immediately moves into the training stage.

## Current User Flow
1. User opens `/chat`.
2. Zito asks profile questions:
   - name and username
   - job, profession, or learning path
3. Each answer is checked by AI.
4. Invalid answers are rejected with guidance and the same question is asked again.
5. Valid answers are stored in the database.
6. When onboarding is complete, Zito generates the first lesson.
7. User sees one unified chat input. There are no separate "question" and "exercise answer" controls.
8. If the message looks like a learning question, Zito answers it with RAG context.
9. Otherwise the message is evaluated as the exercise answer through Arvan AIaaS.
10. If the answer is good enough, Zito silently moves to the next lesson. If not, it gives guidance and asks again.

## Admin Flow
- Admin panel is separate from the user route.
- Users do not see an admin link in the chat UI.
- Admin UI: `GET /admin`
- Admin APIs: `/api/admin/*`
- Admin access is protected with HTTP Basic auth using:
  - `ADMIN_USERNAME`
  - `ADMIN_PASSWORD`

## AI Rule
All LLM calls must go through Arvancloud AIaaS via `src/lib/arvan_client.py`.

Use cases:
- initial onboarding answer validation
- training question validation
- lesson generation with retrieved knowledge context
- training exercise answer evaluation

Direct calls to OpenAI, Anthropic, or similar providers are not allowed.

## Training Scope
The default training knowledge base covers three AI-focused domains:
- accounting and AI
- psychology and AI
- law and AI

## RAG / Knowledge Base
Validation does not need RAG. RAG is used for lesson generation and training answers.

Because there is no company knowledge base yet, the app seeds default internal documents in `src/seed.py`. Later, real company content can be inserted into `knowledge_documents`.

## Stack
- Backend: Python + FastAPI
- Database: SQLite for quick local testing, PostgreSQL for production
- ORM/Migrations: SQLAlchemy + Alembic
- UI: FastAPI-served HTML/CSS/JS

## Important Files
- `src/main.py`: FastAPI app and UI routes
- `src/api/routes.py`: onboarding, admin, and training APIs
- `src/lib/arvan_client.py`: reusable Arvan AIaaS client
- `src/prompts/`: editable system prompts
- `src/seed.py`: default questions and default knowledge documents
- `src/templates/chat.html`: user chat and training UI
- `src/templates/admin.html`: protected admin UI

## Main Endpoints
- `GET /chat`: user chat UI
- `GET /admin`: protected admin UI
- `GET /health`: API and database health check
- `POST /api/onboarding/start`
- `POST /api/onboarding/{user_id}/answer`
- `POST /api/training/{user_id}/lesson`
- `POST /api/training/{user_id}/question`
- `POST /api/training/{user_id}/answer`
- `POST /api/training/{user_id}/message`: unified training chat endpoint used by the UI
- `GET /api/admin/users`
- `PUT /api/admin/answers/{answer_id}`
- `DELETE /api/admin/users/{user_id}`
