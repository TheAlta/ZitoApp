# Security Guide

## Secrets

- Never commit `.env`, API keys, database passwords, SSH passwords, private keys, or production tokens.
- Keep only `.env.example` in Git. It documents required variables with fake values.
- Each developer should create their own local `.env` from `.env.example`.
- Production secrets should live only on the server or a secret manager, not in the repository.

## Required Environment Variables

- `DATABASE_URL`: database connection string.
- `ARVAN_API_BASE_URL`: Arvancloud AIaaS endpoint base URL.
- `ARVAN_API_KEY`: Arvancloud AIaaS API key.
- `ARVAN_MODEL`: model name.
- `ARVAN_TIMEOUT_SECONDS`: outbound AI request timeout.
- `ARVAN_MOCK_AI`: use mocked AI responses for local tests.
- `ADMIN_USERNAME`: initial admin username for first seed.
- `ADMIN_PASSWORD`: initial admin password for first seed.
- `ADMIN_SESSION_SECRET`: secret used to sign admin sessions.
- `ADMIN_SESSION_DAYS`: admin session lifetime.

## Local Setup

```powershell
Copy-Item .env.example .env
```

Then edit `.env` locally and replace every placeholder with real local values.

## Local Password Manager

This repository includes a small local helper at `tools/zito-secrets.ps1`.
It stores secrets in `.secrets/zito-vault.local.json`, which is ignored by Git and encrypted with Windows DPAPI.

Initialize it:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 init
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 import-env
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 set-server-password
```

List saved secret names without revealing values:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 list
```

The SSH server password belongs in this local vault or a real password manager, not in `.env`.

## Production Rules

- Set `APP_ENV=production` on the server.
- Use PostgreSQL for `DATABASE_URL`.
- Use `ARVAN_MOCK_AI=false`.
- Use a strong `ADMIN_PASSWORD` and a long random `ADMIN_SESSION_SECRET`.
- `ADMIN_PASSWORD` is only used when the very first admin is seeded. Existing admins keep their hashed password in the database.
- Rotate any secret that was ever posted in chat, issue trackers, screenshots, or logs.

## Before Push

Run:

```powershell
git status --short
git ls-files -o --exclude-standard
git grep -n -I -E "API_KEY|PASSWORD|SECRET|TOKEN|Bearer"
```

Only placeholders should appear in tracked documentation files.
