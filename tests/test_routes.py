"""End-to-end: every API endpoint through TestClient, providers faked.

The jobs run on background threads, so the network fakes must stay active
until a job is finished: the with-block around a request closes before the
thread's API calls happen otherwise.
"""

import time
import unittest
from unittest import mock

import config as cfg

from app import jobs, settings as web_settings
from tests.support import DikteTest, fake_urlopen, make_wav, silence, speech


class RouteTest(DikteTest):
    """A logged-in TestClient over an isolated config, no fixture involved."""

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app
        self.client = TestClient(fastapi_app)
        self.addCleanup(self.client.close)
        fresh = cfg.Config()
        web_settings.apply(fresh, {"transcribe_provider": "openai",
                                   "openai_api_key": "sk-test",
                                   "openrouter_api_key": "sk-or-test",
                                   "cleanup_enabled": False})
        fastapi_app.state.conf = fresh
        resp = self.client.post("/login", data={"password": "test-password"},
                                follow_redirects=False)
        assert resp.status_code == 303

    def wait_job(self, job_id, timeout=10):
        deadline = time.time() + timeout
        while time.time() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in ("done", "failed"):
                return job
            time.sleep(0.05)
        self.fail("job did not finish")


class Dictation(RouteTest):
    def test_a_recording_comes_back(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)):
            with fake_urlopen({"text": "merhaba"}):
                resp = self.client.post(
                    "/api/dictate",
                    files={"audio": ("rec.webm", b"fake-webm", "audio/webm")})
                self.assertEqual(resp.status_code, 200)
                job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done")
        self.assertIn("merhaba", job["result"]["text"])

    def test_second_job_while_busy_is_409(self):
        held = {}

        def slow_work(emit):
            held["running"] = True
            time.sleep(0.3)
            return {"text": "x"}

        job_id = jobs.submit("dictation", slow_work)
        resp = self.client.post("/api/dictate",
                                files={"audio": ("a.webm", b"x", "audio/webm")})
        self.assertEqual(resp.status_code, 409)
        self.wait_job(job_id)

    def test_busy_upload_cleans_up_the_temp_file(self):
        import app.routes.api as api_routes
        path = self.path("leak-check.bin")
        path.write_bytes(b"x")
        saved = {}

        def fake_save(upload):
            saved["path"] = str(path)
            return str(path)

        with mock.patch.object(api_routes, "_save_upload", side_effect=fake_save):
            held = {}

            def slow(emit):
                held["go"] = True
                time.sleep(0.3)
                return {"text": "x"}

            first = jobs.submit("dictation", slow)
            resp = self.client.post(
                "/api/dictate", files={"audio": ("a.webm", b"x", "audio/webm")})
            self.assertEqual(resp.status_code, 409)
            self.wait_job(first)
        self.assertFalse(path.exists(), "busy path leaked the temp upload")

    def test_unauthenticated_api_is_401(self):
        self.client.cookies.clear()
        resp = self.client.get("/api/history")
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_page_redirects_to_login(self):
        self.client.cookies.clear()
        resp = self.client.get("/dictate", follow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers["location"], "/login")


class Files(RouteTest):
    def test_a_file_transcribes_and_downloads(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)), \
                mock.patch("filetranscribe._to_mp3",
                           side_effect=lambda path, *a, **k: path), \
                mock.patch("filetranscribe.shutil.which",
                           return_value="/usr/bin/ffmpeg"), \
                mock.patch("filetranscribe.api.transcribe",
                           return_value="dosya metni"):
            resp = self.client.post(
                "/api/files/transcribe",
                files={"file": ("clip.mp4", b"fake", "video/mp4")},
                data={"timestamps": "", "cleanup": ""})
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done")
        dl = self.client.get(f"/api/jobs/{job['id']}/download?format=txt")
        self.assertEqual(dl.status_code, 200)
        self.assertIn("dosya metni", dl.text)


class Meetings(RouteTest):
    def test_a_mono_upload_writes_minutes(self):
        clip = make_wav(self.path("meet.wav"), speech(1.0))
        with mock.patch("filetranscribe._ffmpeg") as ff:
            ff.side_effect = lambda *a, **k: str(clip)
            with fake_urlopen(
                {"text": "merhaba toplantı"},
                {"choices": [{"message": {"content": "# Toplantı\n\nÖzet"}}]},
            ):
                resp = self.client.post(
                    "/api/meetings",
                    files={"file": ("meet.wav", b"fake", "audio/wav")},
                    data={"participants": ""})
                job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        rows = cfg.read_meetings()
        self.assertEqual(rows[-1]["status"], "done")
        detail = self.client.get(f"/api/meetings/{rows[-1]['base']}")
        self.assertIn("Toplantı", detail.json()["doc"])


class Agent(RouteTest):
    def test_a_question_is_answered(self):
        with fake_urlopen({"choices": [{"message": {"content": "cevap"}}]}):
            resp = self.client.post("/api/agent", json={"question": "merhaba"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["answer"], "cevap")

    def test_an_empty_question_is_rejected(self):
        resp = self.client.post("/api/agent", json={"question": "  "})
        self.assertEqual(resp.status_code, 400)


class HistorySettings(RouteTest):
    def test_history_lists_and_clears(self):
        cfg.append_history({"ts": "now", "text": "kayıt", "raw": "kayıt"})
        resp = self.client.get("/api/history")
        self.assertEqual(resp.json()["entries"][-1]["text"], "kayıt")
        self.client.post("/api/history/clear")
        self.assertEqual(self.client.get("/api/history").json()["entries"], [])

    def test_settings_round_trip(self):
        resp = self.client.get("/api/settings")
        self.assertIn("settings", resp.json())
        post = self.client.post("/api/settings",
                                json={"settings": {"cleanup_model": "some/model"}})
        self.assertEqual(post.status_code, 200)
        self.assertEqual(cfg.Config()["cleanup_model"], "some/model")


if __name__ == "__main__":
    unittest.main()
