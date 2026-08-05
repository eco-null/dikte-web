import os
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config as cfg
import i18n
import markdown
import nh3

from app import auth
from app.routes import api as api_routes
from app.routes import pages as pages_routes

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

MUTATING_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _markdown_html(text):
    return nh3.clean(markdown.markdown(text or ""))


def _accepted_hosts(request):
    """The hostnames this request may legitimately claim as its own.

    The direct Host header is the obvious one. Behind a reverse proxy the Host
    header is rewritten to the internal name, so the headers proxies put in
    front of it are trusted too: X-Forwarded-Host, and the host= part of the
    Forwarded header. request.url.netloc is a fallback when nothing was set.
    """
    hosts = set()
    direct = request.headers.get("host")
    if direct:
        hosts.add(direct)
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        for part in forwarded_host.split(","):
            hosts.add(part.strip())
    forwarded = request.headers.get("forwarded")
    if forwarded:
        for part in forwarded.split(","):
            for item in part.split(";"):
                key, _, value = item.strip().partition("=")
                if key.lower() == "host":
                    hosts.add(value.strip().strip('"'))
    if request.url.netloc:
        hosts.add(request.url.netloc)
    return hosts


def _same_origin(request):
    accepted = _accepted_hosts(request)
    for header in ("origin", "referer"):
        value = request.headers.get(header)
        if value:
            try:
                return urlsplit(value).netloc in accepted
            except ValueError:
                return False
    return True


def create_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    templates.env.globals["t"] = i18n.t
    templates.env.globals["lang"] = i18n.language
    templates.env.filters["markdown"] = _markdown_html
    app.state.templates = templates

    conf = cfg.Config()
    i18n.set_language(conf["ui_language"])
    app.state.conf = conf

    app.include_router(pages_routes.router)
    app.include_router(api_routes.router)

    @app.middleware("http")
    async def login_gate(request: Request, call_next):
        path = request.url.path
        public = (path == "/login" or path.startswith("/static/")
                  or path == "/healthz")
        if not public and not auth.check(request.cookies.get(auth.COOKIE, "")):
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Not authenticated"}, status_code=401)
            return RedirectResponse("/login", status_code=303)
        return await call_next(request)

    @app.middleware("http")
    async def csrf_protect(request: Request, call_next):
        if request.method in MUTATING_METHODS:
            if request.url.path == "/login":
                return await call_next(request)
            if not _same_origin(request):
                if request.url.path.startswith("/api/"):
                    return JSONResponse(
                        {"detail": "Forbidden: cross-site request"},
                        status_code=403)
                return Response("Forbidden: cross-site request", status_code=403,
                                media_type="text/plain")
        return await call_next(request)

    @app.get("/healthz")
    def healthz():
        try:
            cfg.Config()
            return {"ok": True}
        except Exception:
            return JSONResponse({"ok": False, "error": "settings unavailable"},
                                status_code=500)

    return app


app = create_app()
