from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.config import get_settings
from src.db import Base, SessionLocal, engine
from src.models import CourseVersion
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
    with SessionLocal() as db:
        interrupted = db.query(CourseVersion).filter(
            CourseVersion.generation_status == "generating"
        ).all()
        for version in interrupted:
            version.generation_status = "failed"
            version.generation_error = "تولید قبلی با توقف سرویس نیمه‌کاره ماند؛ دوباره تولید را شروع کن."
        if interrupted:
            db.commit()


SPA_INDEX = LANDING_ROOT / "app" / "index.html"


def _spa() -> HTMLResponse:
    """Every page is the single-page app; its router reads the URL. Assets are hashed, the shell is not cached."""
    return HTMLResponse(SPA_INDEX.read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    return _spa()


@app.get("/chat", response_class=HTMLResponse)
def legacy_chat_ui(request: Request):
    query = f"?{request.url.query}" if request.url.query else ""
    return RedirectResponse(f"/app/{query}", status_code=303)


@app.get("/app", response_class=HTMLResponse)
@app.get("/app/{page_path:path}", response_class=HTMLResponse)
def app_ui(page_path: str = "") -> HTMLResponse:
    return _spa()


@app.get("/certificate", response_class=HTMLResponse)
@app.get("/certificate/{certificate_number}", response_class=HTMLResponse)
def certificate_ui(certificate_number: str = "") -> HTMLResponse:
    return _spa()


@app.get("/admin", response_class=HTMLResponse)
@app.get("/admin/{page_path:path}", response_class=HTMLResponse)
def admin_ui(page_path: str = "") -> HTMLResponse:
    return _spa()
