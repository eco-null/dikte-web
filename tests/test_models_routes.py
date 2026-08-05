

import time
import unittest
from unittest import mock

import config as cfg
import ggml
import hub
from app import jobs, settings as web_settings
from tests.support import DikteTest, fake_urlopen

class ModelsTest(DikteTest):
    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app
        self.client = TestClient(fastapi_app)
        self.addCleanup(self.client.close)
        fresh = cfg.Config()
        web_settings.apply(fresh, {"cleanup_enabled": False})
        fastapi_app.state.conf = fresh
        self.client.post("/login", data={"password": "test-password"})
        self.patch_attr(ggml, "DATA_DIR", self.path("data"))
        self.patch_attr(ggml, "BIN_DIR", self.path("data", "bin"))
        self.patch_attr(ggml, "MODELS_DIR", self.path("data", "models"))
        self.patch_attr(hub, "CACHE_DIR", self.path("cache"))

    def test_catalog_lists_models(self):
        with _files_reply([hub.Item("ggml-small.bin", "https://x/s", 100, "a")]):
            resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200)
        names = [m["name"] for m in resp.json()["whisper_models"]]
        self.assertIn("ggml-small.bin", names)

    def test_catalog_degrades_on_network_failure(self):
        with mock.patch("ggml.whisper_models",
                        side_effect=ggml.LocalError("offline")):
            resp = self.client.get("/api/models")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["whisper_models"], [])

    def test_install_program_returns_a_job(self):
        with mock.patch("ggml.install_program") as inst:
            inst.return_value = "/data/bin/whisper/b1/whisper-server"
            resp = self.client.post("/api/models/install",
                                    json={"kind": "program", "name": "whisper"})
            job = self._wait(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        self.assertIn("whisper-server", job["result"]["path"])

    def test_install_while_busy_is_409(self):
        held = {}

        def slow(emit):
            held["go"] = True
            time.sleep(0.3)
            return {"path": "/x"}

        first = jobs.submit("model", slow)
        resp = self.client.post("/api/models/install",
                                json={"kind": "program", "name": "whisper"})
        self.assertEqual(resp.status_code, 409)
        self._wait(first)

    def test_delete_removes_a_model(self):
        p = self.path("data", "models", "whisper", "ggml-x.bin")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        resp = self.client.post("/api/models/delete", json={"path": str(p)})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(p.exists())

    def test_delete_refuses_a_path_outside_models_dir(self):
        p = self.path("data", "config.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"keep me")
        resp = self.client.post("/api/models/delete", json={"path": str(p)})
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(p.exists())

    def test_install_whisper_persists_the_selection(self):
        item = hub.Item("ggml-small.bin", "https://x/s", 100, "a")
        with _files_reply([item]):
            with mock.patch("ggml.download", return_value=True):
                resp = self.client.post(
                    "/api/models/install",
                    json={"kind": "whisper", "name": "ggml-small.bin"})
                job = self._wait(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        self.assertTrue(job["result"]["installed"])
        fresh = cfg.Config()
        self.assertEqual(fresh["local_model"], "ggml-small.bin")

    def test_llm_install_rejects_a_repo_outside_the_allowlist(self):
        with mock.patch("ggml.llm_repos",
                        return_value=["ggml-org/gemma-3-4b-it-GGUF"]):
            resp = self.client.post(
                "/api/models/install",
                json={"kind": "llm", "repo": "evil/llama",
                      "name": "x-Q4_K_M.gguf"})
        self.assertEqual(resp.status_code, 400)

    def test_llm_install_accepts_a_known_repo(self):
        item = hub.Item("x-Q4_K_M.gguf", "https://x/s", 100, "a")
        with _files_reply([item]):
            with mock.patch("ggml.llm_repos",
                            return_value=["ggml-org/gemma-3-4b-it-GGUF"]), \
                    mock.patch("ggml.download", return_value=True):
                resp = self.client.post(
                    "/api/models/install",
                    json={"kind": "llm", "repo": "ggml-org/gemma-3-4b-it-GGUF",
                          "name": "x-Q4_K_M.gguf"})
                job = self._wait(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        fresh = cfg.Config()
        self.assertEqual(fresh["local_llm_model"], "x-Q4_K_M.gguf")

    def test_program_install_rejects_an_unknown_program(self):
        resp = self.client.post("/api/models/install",
                                json={"kind": "program", "name": "evil"})
        self.assertEqual(resp.status_code, 400)

    def _wait(self, job_id, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in ("done", "failed"):
                return job
            time.sleep(0.05)
        self.fail("job did not finish")

def _files_reply(items):
    import json
    body = [{"type": "file", "path": it.name,
             "lfs": {"size": it.size, "oid": "sha256:" + it.sha256},
             "downloadUrl": it.url} for it in items]
    return fake_urlopen(json.loads(json.dumps(body)))

if __name__ == "__main__":
    unittest.main()
