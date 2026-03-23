import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from schemas.reservation import RESERVATION_CITY_BODY_SCHEMA

from api.admin_reservations import router as admin_reservations_router
from api.auth import router as auth_router
from api.my_reservations import router as my_reservations_router
from api.pages import frontend_dir, router as pages_router
from api.reservations import router as reservations_router
from infrastructure.database import init_db

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    fd = frontend_dir()
    login_path = fd / "login.html"
    if not login_path.is_file():
        logger.error(
            "login.html not found at %s (FRONTEND_DIR=%s). Fix project layout or sync files.",
            login_path,
            fd.resolve(),
        )
    else:
        logger.info("Serving UI from %s", fd.resolve())
    _port = os.getenv("PORT", "8010")
    logger.info(
        "Worker PID=%s (PORT=%s). If /login is 404 in browser, another process may be bound to this port or a proxy is intercepting.",
        os.getpid(),
        _port,
    )
    yield


app = FastAPI(title="Hotel reservation requests", lifespan=lifespan)

_ui_root = frontend_dir()


@app.get("/Loga/Logo-negativni-RGB.png", include_in_schema=False)
def serve_header_logo_png():
    """Explicit route for Direct negative RGB logo on dark header bar."""
    p = _ui_root / "Loga" / "Logo-negativni-RGB.png"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(p, media_type="image/png")


# Static UI and logos before API routers so paths like /Loga/* are never shadowed.
if _ui_root.is_dir():
    _assets = _ui_root / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")
    app.mount("/css", StaticFiles(directory=str(_ui_root / "css")), name="css")
    app.mount("/js", StaticFiles(directory=str(_ui_root / "js")), name="js")
    _loga = _ui_root / "Loga"
    if _loga.is_dir():
        app.mount("/Loga", StaticFiles(directory=str(_loga)), name="loga")


@app.middleware("http")
async def add_hotel_identity_header(request: Request, call_next):
    """So you can tell in DevTools (Network → Headers) if the response is from this app."""
    response = await call_next(request)
    response.headers["X-Hotel-App"] = "hotel-reservations"
    response.headers["X-Hotel-Pid"] = str(os.getpid())
    return response


@app.get("/__hotel_ready", include_in_schema=False)
@app.get("/_hotel_ready", include_in_schema=False)
def hotel_ready():
    """Sanity check that this codebase is the one bound to the port (open in browser)."""
    return {
        "app": "hotel-reservations",
        "login_path": "/login",
        "reservation_city_body": RESERVATION_CITY_BODY_SCHEMA,
    }


@app.get("/login", include_in_schema=False)
@app.get("/login.html", include_in_schema=False)
def serve_login_html():
    # Registered on the root app so /login is always tied to this module.
    p = frontend_dir() / "login.html"
    if not p.is_file():
        logger.error("login.html missing at %s", p.resolve())
        return HTMLResponse(
            (
                "<!DOCTYPE html><html lang='cs'><head><meta charset='utf-8'><title>Chyba</title></head>"
                "<body style='font-family:system-ui;padding:2rem'>"
                f"<h1>Chybí soubor login.html</h1><p>Očekáváno: {p.resolve()}</p>"
                "<p>Spusť server ze složky projektu, kde vedle <code>backend</code> leží <code>frontend</code>.</p>"
                "</body></html>"
            ),
            status_code=500,
        )
    return FileResponse(p)


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(reservations_router, prefix="/reservations", tags=["reservations"])
app.include_router(my_reservations_router, prefix="/my", tags=["my"])
app.include_router(
    admin_reservations_router, prefix="/admin/reservations", tags=["admin"]
)
# HTML pages last among routers so they do not shadow API paths
app.include_router(pages_router)

_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


_route_paths = [getattr(r, "path", None) for r in app.routes]
assert "/login" in _route_paths, "BUG: /login route not registered"
assert "/__hotel_ready" in _route_paths, "BUG: /__hotel_ready route not registered"


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8010"))
    # Default off: reload spawns an extra process on Windows and confused debugging when port 8003 was busy.
    _reload = os.getenv("UVICORN_RELOAD", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    uvicorn.run("main:app", host=host, port=port, reload=_reload)
