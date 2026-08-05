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

PROVIDER_ORDER = ["openai", "groq", "openrouter", "omniroute", "local"]
SERVICE_ORDER = ["transcribe", "cleanup", "assistant"]

GENERAL_KEYS = [
    "ui_language", "transcribe_prompt",
    "skip_silent", "silence_db", "speech_margin_db",
    "min_voiced_seconds", "filter_hallucinations",
    "history_limit", "mic_target", "keep_audio",
    "max_seconds", "file_timestamps", "file_cleanup",
    "file_cleanup_prompt", "cleanup_enabled",
    "cleanup_reasoning", "cleanup_prompt",
    "assistant_reasoning", "assistant_prompt",
    "assistant_session_minutes", "assistant_timeout",
]

MEETING_KEYS = [
    "meeting_cleanup", "meeting_model", "meeting_reasoning",
    "meeting_prompt", "meeting_max_seconds", "meeting_keep_audio",
    "meeting_self_name", "meeting_other_name", "meeting_participants",
]


def _service_spec(service):
    spec = {
        "key": service,
        "title": {
            "transcribe": "Transcription",
            "cleanup": "Cleanup",
            "assistant": "Assistant",
        }[service],
        "providers": [],
    }
    for p in PROVIDER_ORDER:
        spec["providers"].append({"name": p})
    return spec


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
    import config as cfg
    services = [_service_spec(s) for s in SERVICE_ORDER]
    display = web_settings.present(request.app.state.conf)
    prompt_defaults = {
        "file_cleanup_prompt": cfg.default_file_cleanup_prompt,
        "cleanup_prompt": cfg.default_cleanup_prompt,
        "meeting_prompt": cfg.default_meeting_prompt,
        "assistant_prompt": cfg.default_assistant_prompt,
    }
    for key, factory in prompt_defaults.items():
        if not (display.get(key) or "").strip():
            display[key] = factory()
    return _render(request, "settings.html", {
        "fields": web_settings.WEB_FIELDS,
        "settings": display,
        "masked": web_settings.MASKED,
        "conf": request.app.state.conf,
        "services": services,
        "general_keys": GENERAL_KEYS,
        "meeting_keys": MEETING_KEYS,
    })
