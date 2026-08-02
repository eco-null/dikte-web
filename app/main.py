"""FastAPI uygulaması.

- /static ve /healthz hariç her şey auth gate'ten geçer (/api/* -> 401, sayfalar -> /login).
- Jinja2'ye `t` globali ve `markdown` filtresi eklenir.
- app.state.conf: webapp'in paylaşılan Config'i.
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config as cfg
import i18n
import markdown

from app import auth
from app.routes import api as api_routes
from app.routes import pages as pages_routes

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")


def create_app():
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    templates = Jinja2Templates(directory=TEMPLATE_DIR)
    templates.env.globals["t"] = i18n.t
    templates.env.globals["lang"] = i18n.language
    templates.env.filters["markdown"] = markdown.markdown
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

    @app.get("/healthz")
    def healthz():
        try:
            cfg.Config()  # config dosyası okunabiliyor mu?
            return {"ok": True}
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=500)

    return app


app = create_app()
