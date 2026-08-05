import hmac
import os
import threading
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import auth

router = APIRouter()

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW = 15 * 60
_login_failures = {}
_login_failures_lock = threading.Lock()

SECTIONS = {
    "Transcription": ["ui_language", "transcribe_provider",
                      "transcribe_model",
                      "groq_transcribe_model", "openrouter_transcribe_model",
                      "openai_api_key", "groq_api_key", "openrouter_api_key",
                      "language", "transcribe_prompt", "max_seconds",
                      "skip_silent", "silence_db", "speech_margin_db",
                      "min_voiced_seconds", "filter_hallucinations",
                      "mic_target", "keep_audio", "file_timestamps",
                      "file_cleanup", "file_cleanup_prompt", "history_limit"],
    "Cleanup": ["cleanup_enabled", "cleanup_provider", "cleanup_model",
                "cleanup_reasoning", "cleanup_prompt"],
    "Local models": ["local_model", "local_threads", "local_gpu",
                     "local_preload", "local_llm_model", "local_llm_threads",
                     "local_llm_gpu", "local_llm_context",
                     "local_llm_preload", "local_llm_reasoning"],
    "Meetings": ["meeting_cleanup", "meeting_model", "meeting_reasoning",
                 "meeting_prompt", "meeting_self_name", "meeting_other_name",
                 "meeting_participants", "meeting_max_seconds",
                 "meeting_keep_audio"],
    "Assistant": ["assistant_provider", "assistant_openrouter_model",
                  "assistant_omniroute_base_url", "assistant_omniroute_model",
                  "assistant_omniroute_api_key",
                  "assistant_session_minutes", "assistant_timeout",
                  "assistant_reasoning", "assistant_prompt"],
}


def _env_bool(name, default):
    return str(os.environ.get(name, default)).lower() in ("1", "true", "on", "yes")


def _render(request, template, context=None, status_code=200):
    ctx = dict(context or {})
    ctx.setdefault("current_path", request.url.path)
    return request.app.state.templates.TemplateResponse(
        request, template, ctx, status_code=status_code)


def _client_ip(request):
    forwarded = request.headers.get("cf-connecting-ip") or \
        (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "")


def _too_many_login_failures(ip):
    with _login_failures_lock:
        now = time.time()
        stamps = [ts for ts in _login_failures.get(ip, [])
                  if now - ts < LOGIN_WINDOW]
        if not stamps:
            _login_failures.pop(ip, None)
            return False
        _login_failures[ip] = stamps
        return len(stamps) >= LOGIN_MAX_FAILURES


def _record_login_failure(ip):
    with _login_failures_lock:
        now = time.time()
        stamps = [ts for ts in _login_failures.get(ip, [])
                  if now - ts < LOGIN_WINDOW]
        stamps.append(now)
        _login_failures[ip] = stamps


def _reset_login_failures(ip=None):
    with _login_failures_lock:
        if ip is None:
            _login_failures.clear()
        else:
            _login_failures.pop(ip, None)


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
    ip = _client_ip(request)
    if _too_many_login_failures(ip):
        return _render(request, "login.html",
                       {"error": "Too many failed attempts. Try again later."},
                       status_code=429)
    if not hmac.compare_digest(password, auth.password()):
        _record_login_failure(ip)
        return _render(request, "login.html",
                       {"error": "Wrong password."})
    _reset_login_failures(ip)
    response = RedirectResponse("/dictate", status_code=303)
    response.set_cookie(auth.COOKIE, auth.new_session(), httponly=True,
                        samesite="lax",
                        secure=_env_bool("DIKTE_COOKIE_SECURE", "1"),
                        max_age=auth.SESSION_HOURS * 3600)
    return response


@router.get("/logout")
@router.post("/logout")
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
        "sections": SECTIONS,
        "settings": web_settings.present(request.app.state.conf),
        "masked": web_settings.MASKED,
        "conf": request.app.state.conf,
    })
