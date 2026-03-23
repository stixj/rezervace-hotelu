"""
Browser UI routes (HTML). Kept in api/ layer as HTTP-only; no business logic here.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, RedirectResponse

# backend/api/pages.py -> backend -> project root -> frontend
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

router = APIRouter(include_in_schema=False)


def _page(name: str) -> FileResponse:
    return FileResponse(_FRONTEND_DIR / name)


def frontend_dir() -> Path:
    return _FRONTEND_DIR


@router.get("/")
def root_page(request: Request):
    base = str(request.base_url).rstrip("/")
    return RedirectResponse(url=f"{base}/login", status_code=302)


@router.get("/index.html")
def legacy_index(request: Request):
    base = str(request.base_url).rstrip("/")
    return RedirectResponse(url=f"{base}/login", status_code=302)


@router.get("/app/new")
def app_new_page():
    return _page("app_new.html")


@router.get("/app/my-requests")
def app_my_requests_page():
    return _page("app_my_requests.html")


@router.get("/app/requests/{reservation_id}")
def app_request_detail_page(reservation_id: str):
    return _page("app_request_detail.html")


@router.get("/admin/requests")
def admin_requests_page():
    return _page("admin_requests.html")


@router.get("/admin/requests/{reservation_id}")
def admin_request_detail_page(reservation_id: str):
    return _page("admin_request_detail.html")
