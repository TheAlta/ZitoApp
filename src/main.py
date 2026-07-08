from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse

from src.api.routes import router
from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.security import require_admin
from src.seed import seed_defaults

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(router)

ROOT = Path(__file__).resolve().parent


@app.on_event("startup")
def startup() -> None:
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed_defaults(db)


def _html(name: str) -> HTMLResponse:
    return HTMLResponse((ROOT / "templates" / name).read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return _html("chat.html")


@app.get("/chat", response_class=HTMLResponse)
def chat_ui() -> HTMLResponse:
    return _html("chat.html")


@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def admin_ui() -> HTMLResponse:
    return _html("admin.html")
