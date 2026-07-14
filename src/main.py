from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.config import get_settings
from src.db import Base, SessionLocal, engine, get_db
from src.security import get_admin_from_request
from src.seed import seed_defaults

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(router)

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
LANDING_ROOT = PROJECT_ROOT / "landing"

if LANDING_ROOT.exists():
    app.mount("/landing-static", StaticFiles(directory=LANDING_ROOT), name="landing-static")


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
    landing = LANDING_ROOT / "zito.html"
    if landing.exists():
        return HTMLResponse(landing.read_text(encoding="utf-8"))
    return _html("chat.html")


@app.get("/chat", response_class=HTMLResponse)
def chat_ui() -> HTMLResponse:
    return _html("chat.html")


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_ui() -> HTMLResponse:
    return _html("admin_login.html")


@app.get("/admin", response_class=HTMLResponse)
def admin_ui(request: Request, db=Depends(get_db)):
    if not get_admin_from_request(request, db):
        return RedirectResponse("/admin/login", status_code=303)
    return _html("admin.html")
