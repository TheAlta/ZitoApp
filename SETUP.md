# Zito Setup

## Fast Local Test Without PostgreSQL
Use this path first. It runs the app with a local SQLite file and mock AI.

```powershell
cd C:\Users\ASUS\Desktop\ZitoApp
$env:DATABASE_URL="sqlite:///./local_test.db"
$env:ARVAN_MOCK_AI="true"
$env:ADMIN_USERNAME="zito_admin"
$env:ADMIN_PASSWORD="change-me"
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

Open in browser:
- User chat: `http://127.0.0.1:8000/chat`
- Admin panel: `http://127.0.0.1:8000/admin`
- API docs: `http://127.0.0.1:8000/docs`

Admin login for local test:
- username: `zito_admin`
- password: `change-me`

## What To Test In The Browser
1. Open `/chat`.
2. Enter an invalid answer like `asdf`; Zito should reject it and show guidance.
3. Enter a valid name and username.
4. Enter a valid profession.
5. Zito should immediately generate a lesson in one of three tracks: accounting, psychology, or law with AI.
6. In the same input, either ask a question or answer the exercise. There is no separate mode switch.
7. If your answer is good enough, Zito moves to the next lesson. If not, it gives guidance and asks again.
8. Open `/admin`; the browser should ask for admin username and password.
9. After login, you should see saved users and answers.

## Real Arvan Mode
Create `.env` from `.env.example` and set:

```env
DATABASE_URL=sqlite:///./local_test.db
ARVAN_MOCK_AI=false
ARVAN_API_BASE_URL=https://arvancloudai.ir/gateway/models/GPT-5.4-Mini/YOUR_ENDPOINT_TOKEN/v1
ARVAN_API_KEY=your_real_key
ARVAN_MODEL=GPT-5.4-Mini
ADMIN_USERNAME=zito_admin
ADMIN_PASSWORD=choose_a_strong_password
```

Important: do not commit `.env`. If an API key was shared in chat, rotate it in Arvan and use a new one.

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
```

Run migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

## Stop The Server
In the PowerShell window where Uvicorn is running, press:

```text
Ctrl + C
```
