# Zito Deployment Assets

This directory contains deploy-time templates. It never contains credentials,
production environment files, database dumps, or private keys.

## RAG indexing worker

`systemd/zito-rag-indexer.service` runs the existing durable RAG worker as a
separate process. It does not change learner-facing requests: approved KB
documents create rows in `course_kb_index_jobs`, and this service turns queued
jobs into indexed embeddings.

Before installing the unit on production:

1. Deploy the same Git revision as the main `zito` service.
2. Run Alembic migrations successfully.
3. Confirm `/health` is healthy and run the private `verify-rag` command.
4. Confirm `/opt/zito/app/.env` contains the required embedding configuration.

Install it only during an approved deployment window:

```bash
cd /opt/zito/app
sudo install -m 0644 deploy/systemd/zito-rag-indexer.service /etc/systemd/system/zito-rag-indexer.service
sudo systemctl daemon-reload
sudo systemctl enable --now zito-rag-indexer
sudo systemctl status zito-rag-indexer --no-pager
```

Operational checks:

```bash
sudo journalctl -u zito-rag-indexer -n 100 --no-pager
sudo systemctl is-active zito-rag-indexer
```

To stop it safely, disable only the worker; do not stop the main web service:

```bash
sudo systemctl disable --now zito-rag-indexer
```
