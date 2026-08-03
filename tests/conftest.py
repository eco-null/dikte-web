"""Test ortamı: bare-name shim'in yüklenmesi, env, TestClient fixture.

app.main import edilmeden önce DIKTE_WEB_PASSWORD ve XDG yolları kurulur
(vendored config yolları import anında hesaplanır).
"""

import os
import pathlib
import tempfile

os.environ["DIKTE_WEB_PASSWORD"] = "test-password"
# TestClient speaks http://testserver, and httpx will not send a Secure cookie
# over plain http; disable the production Secure flag so session tests work.
os.environ["DIKTE_COOKIE_SECURE"] = "0"
_DATA = pathlib.Path(tempfile.mkdtemp(prefix="dikte-web-test-"))
os.environ["XDG_CONFIG_HOME"] = str(_DATA / "config")
os.environ["XDG_DATA_HOME"] = str(_DATA / "data")

import app  # noqa: F401  (bare-name sys.modules shim'i)
from app.main import app as fastapi_app  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def client():
    with TestClient(fastapi_app) as c:
        resp = c.post("/login", data={"password": "test-password"})
        assert resp.status_code == 303
        yield c
