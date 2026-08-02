"""HTML sayfaları. Auth gate main.py'deki middleware'dedir; /login hariç
buradan sunulan her şey zaten oturumludur."""

import hmac

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import auth

router = APIRouter()


def _render(request, template, context=None):
    return request.app.state.templates.TemplateResponse(
        request, template, context or {})


@router.get("/")
def index():
    return RedirectResponse("/dictate", status_code=303)


@router.get("/login")
def login_page(request: Request):
    if auth.check(request.cookies.get(auth.COOKIE, "")):
        return RedirectResponse("/dictate", status_code=303)
    return _render(request, "login.html", {"error": ""})


@router.post("/login")
def login_post(request: Request, password: str = Form("")):
    if not hmac.compare_digest(password, auth.password()):
        return _render(request, "login.html",
                       {"error": "Wrong password."})
    response = RedirectResponse("/dictate", status_code=303)
    response.set_cookie(auth.COOKIE, auth.new_session(), httponly=True,
                        samesite="lax", max_age=auth.SESSION_HOURS * 3600)
    return response


@router.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(auth.COOKIE)
    return response


@router.get("/dictate")
def dictate_page(request: Request):
    return _render(request, "dictation.html",
                   {"conf": request.app.state.conf})


@router.get("/files")
def files_page(request: Request):
    return _render(request, "files.html", {"conf": request.app.state.conf})


@router.get("/meetings")
def meetings_page(request: Request):
    import config as cfg
    rows = cfg.read_meetings()
    rows.reverse()
    return _render(request, "meetings.html",
                   {"meetings": rows, "conf": request.app.state.conf})


@router.get("/meetings/{base}")
def meeting_detail_page(request: Request, base: str):
    import config as cfg
    row = next((r for r in cfg.read_meetings() if r["base"] == base), None)
    if row is None:
        from fastapi import HTTPException
        raise HTTPException(404)
    doc_path = cfg.meeting_paths(base)[0]
    doc = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    return _render(request, "meeting_detail.html",
                   {"meeting": row, "doc": doc})


@router.get("/agent")
def agent_page(request: Request):
    return _render(request, "agent.html", {"conf": request.app.state.conf})


@router.get("/history")
def history_page(request: Request):
    import config as cfg
    rows = cfg.read_history()
    rows.reverse()
    return _render(request, "history.html",
                   {"entries": rows, "conf": request.app.state.conf})


@router.get("/settings")
def settings_page(request: Request):
    from app import settings as web_settings
    return _render(request, "settings.html", {
        "fields": web_settings.WEB_FIELDS,
        "settings": web_settings.present(request.app.state.conf),
        "masked": web_settings.MASKED,
        "conf": request.app.state.conf,
    })
