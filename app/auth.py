import hashlib
import hmac
import os
import secrets
import sys
import time

import config as cfg

COOKIE = "dikte_session"
SESSION_HOURS = 24 * 7
_pepper = secrets.token_bytes(32)


def password():
    stored = os.environ.get("DIKTE_WEB_PASSWORD", "").strip()
    if stored:
        return stored
    try:
        saved = (cfg.DATA_DIR / "web_password").read_text().strip()
        if saved:
            return saved
    except OSError:
        pass
    generated = secrets.token_urlsafe(9)
    try:
        cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        target = cfg.DATA_DIR / "web_password"
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(generated)
    except OSError:
        print("dikte-web: no password configured and could not store one", file=sys.stderr)
    return generated


def _sig(value):
    return hmac.new(_pepper, value.encode(), hashlib.sha256).hexdigest()


def new_session() -> str:
    value = f"{time.time()}.{secrets.token_urlsafe(16)}"
    return f"{value}.{_sig(value)}"


def check(token) -> bool:
    if not token:
        return False
    try:
        value, sig = token.rsplit(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(_sig(value), sig):
        return False
    try:
        ts = float(value.split(".", 1)[0])
    except ValueError:
        return False
    return time.time() - ts < SESSION_HOURS * 3600
