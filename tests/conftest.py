

import os
import pathlib
import tempfile

os.environ["DIKTE_WEB_PASSWORD"] = "test-password"
os.environ["DIKTE_COOKIE_SECURE"] = "0"
_DATA = pathlib.Path(tempfile.mkdtemp(prefix="dikte-web-test-"))
os.environ["XDG_CONFIG_HOME"] = str(_DATA / "config")
os.environ["XDG_DATA_HOME"] = str(_DATA / "data")

import app
from app.main import app as fastapi_app

from fastapi.testclient import TestClient

import pytest

@pytest.fixture
def client():
    with TestClient(fastapi_app) as c:
        resp = c.post("/login", data={"password": "test-password"})
        assert resp.status_code == 303
        yield c
