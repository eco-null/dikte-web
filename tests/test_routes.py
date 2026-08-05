

import io
import os
import time
import unittest
from unittest import mock

from fastapi import HTTPException

import config as cfg

from app import jobs, settings as web_settings
from tests.support import DikteTest, fake_urlopen, make_wav, silence, speech

class RouteTest(DikteTest):

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app.main import app as fastapi_app
        self.client = TestClient(fastapi_app)
        self.addCleanup(self.client.close)
        fresh = cfg.Config()
        fresh["transcribe_openai_key"] = "sk-test"
        fresh["cleanup_openrouter_key"] = "sk-or-test"
        fresh["assistant_openrouter_key"] = "sk-or-test"
        fresh["openrouter_api_key"] = "sk-or-test"
        web_settings.apply(fresh, {"transcribe_provider": "openai",
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

    def test_a_recording_longer_than_the_limit_fails(self):
        clip = make_wav(self.path("long.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)), \
                mock.patch("filetranscribe.wav_seconds",
                           return_value=4 * 3600 + 1):
            resp = self.client.post(
                "/api/dictate",
                files={"audio": ("rec.webm", b"fake-webm", "audio/webm")})
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "failed")
        self.assertIn("4 hour limit", job["error"])

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

    def test_local_transcription_uses_the_local_server(self):
        conf = cfg.Config()
        web_settings.apply(conf, {"transcribe_provider": "local",
                                  "cleanup_enabled": False})
        conf["transcribe_local_model"] = "ggml-small.bin"
        from app.main import app as fastapi_app
        fastapi_app.state.conf = conf
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)), \
                mock.patch("ggml.whisper.configure") as cfgw, \
                mock.patch("api.serving", return_value="http://127.0.0.1:9999/v1") as svc, \
                mock.patch("api._request", return_value={"text": "yerel metin"}):
            resp = self.client.post(
                "/api/dictate",
                files={"audio": ("rec.webm", b"fake-webm", "audio/webm")})
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        self.assertIn("yerel metin", job["result"]["text"])
        cfgw.assert_called()

    def test_local_transcription_uses_per_service_keys(self):
        conf = cfg.Config()
        web_settings.apply(conf, {"transcribe_provider": "local",
                                  "cleanup_enabled": False})
        conf["transcribe_local_model"] = "ggml-small.bin"
        from app.main import app as fastapi_app
        fastapi_app.state.conf = conf
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)), \
                mock.patch("ggml.whisper.configure") as cfgw, \
                mock.patch("api.serving", return_value="http://127.0.0.1:9999/v1"), \
                mock.patch("api._request", return_value={"text": "yerel"}):
            resp = self.client.post(
                "/api/dictate",
                files={"audio": ("rec.webm", b"fake-webm", "audio/webm")})
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        kwargs = cfgw.call_args.kwargs
        self.assertEqual(kwargs["model"], "ggml-small.bin")

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

    def test_a_file_longer_than_the_limit_fails(self):
        clip = make_wav(self.path("long.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav", return_value=str(clip)), \
                mock.patch("filetranscribe.wav_seconds",
                           return_value=4 * 3600 + 1), \
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
        self.assertEqual(job["status"], "failed")
        self.assertIn("4 hour limit", job["error"])

class Downloads(RouteTest):
    def test_download_404_for_unknown_job(self):
        resp = self.client.get("/api/jobs/does-not-exist/download")
        self.assertEqual(resp.status_code, 404)

    def test_download_404_for_a_failed_job(self):
        clip = make_wav(self.path("clip.wav"), speech(1.0))
        with mock.patch("filetranscribe._to_wav",
                        side_effect=RuntimeError("ffmpeg missing")):
            resp = self.client.post(
                "/api/files/transcribe",
                files={"file": ("clip.mp4", b"fake", "video/mp4")})
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "failed")
        dl = self.client.get(f"/api/jobs/{job['id']}/download")
        self.assertEqual(dl.status_code, 404)

    def test_an_oversized_upload_is_413(self):
        import app.routes.api as api_routes
        with mock.patch.object(api_routes, "MAX_UPLOAD", 4):
            resp = self.client.post(
                "/api/dictate",
                files={"audio": ("big.webm", b"x" * 100, "audio/webm")})
        self.assertEqual(resp.status_code, 413)

    def test_an_upload_streamed_past_the_limit_is_413(self):
        import app.routes.api as api_routes
        upload = mock.Mock()
        upload.size = None
        upload.filename = "big.webm"
        upload.file = io.BytesIO(b"x" * 100)
        leak = self.path("leak.bin")
        with mock.patch.object(api_routes, "MAX_UPLOAD", 4), \
                mock.patch("app.routes.api.tempfile.mkstemp",
                           return_value=(os.open(os.devnull, os.O_RDONLY),
                                         str(leak))):
            with self.assertRaises(HTTPException) as cm:
                api_routes._save_upload(upload)
        self.assertEqual(cm.exception.status_code, 413)
        self.assertFalse(leak.exists(), "413 left the temp upload behind")

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

    def test_delete_and_unknown_meeting(self):
        base = "20260101-120000"
        cfg.save_meeting({"base": base, "status": "recorded", "title": ""})
        resp = self.client.delete(f"/api/meetings/{base}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(base, [r["base"] for r in cfg.read_meetings()])
        resp = self.client.delete(f"/api/meetings/{base}")
        self.assertEqual(resp.status_code, 404)

    def test_meeting_delete_with_a_traversal_base_is_rejected(self):
        victim = cfg.meeting_paths("..\\..\\etc\\somefile")[0].resolve()
        victim.parent.mkdir(parents=True, exist_ok=True)
        victim.write_text("keep me", encoding="utf-8")
        resp = self.client.delete("/api/meetings/..%5C..%5Cetc%5Csomefile")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(victim.exists(),
                        "traversal deleted a file outside the meetings dir")

    def test_meeting_detail_404(self):
        resp = self.client.get("/api/meetings/19990101-000000")
        self.assertEqual(resp.status_code, 404)

    def test_retry_reruns_the_pipeline(self):
        base = "20260101-130000"
        wav = self.path("meet.wav")
        make_wav(wav, speech(1.0))
        cfg.save_meeting({"base": base, "status": "failed", "title": "",
                          "error": "old error"})
        cfg.meeting_paths(base)[1].parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(wav, cfg.meeting_paths(base)[1])
        with mock.patch("filetranscribe._ffmpeg") as ff:
            ff.side_effect = lambda *a, **k: str(wav)
            with fake_urlopen(
                {"text": "merhaba"},
                {"choices": [{"message": {"content": "# Toplantı\n\nÖzet"}}]},
            ):
                resp = self.client.post(f"/api/meetings/{base}/retry")
                job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)

    def test_retry_hydrates_the_local_server(self):
        conf = cfg.Config()
        web_settings.apply(conf, {"transcribe_provider": "local",
                                  "cleanup_enabled": False})
        conf["cleanup_openrouter_key"] = "sk-or-test"
        conf["openrouter_api_key"] = "sk-or-test"
        conf["transcribe_local_model"] = "ggml-small.bin"
        from app.main import app as fastapi_app
        fastapi_app.state.conf = conf
        base = "20260101-140000"
        wav = self.path("meet.wav")
        make_wav(wav, speech(1.0))
        cfg.save_meeting({"base": base, "status": "failed", "title": "",
                          "error": "old error"})
        cfg.meeting_paths(base)[1].parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(wav, cfg.meeting_paths(base)[1])

        def fake_request(url, data, headers, timeout=120, aborter=None):
            if "/chat/completions" in url:
                return {"choices": [{"message": {"content": "# Toplantı\n\nÖzet"}}]}
            return {"segments": [{"start": 0.0, "end": 1.0,
                                  "text": "yerel metin"}]}

        with mock.patch("filetranscribe._ffmpeg") as ff, \
                mock.patch("ggml.whisper.configure") as cfgw, \
                mock.patch("api.serving",
                           return_value="http://127.0.0.1:9999/v1"), \
                mock.patch("api._request", side_effect=fake_request):
            ff.side_effect = lambda *a, **k: str(wav)
            resp = self.client.post(f"/api/meetings/{base}/retry")
            job = self.wait_job(resp.json()["job_id"])
        self.assertEqual(job["status"], "done", job)
        cfgw.assert_called()

class Agent(RouteTest):
    def test_a_question_is_answered(self):
        with fake_urlopen({"choices": [{"message": {"content": "cevap"}}]}):
            resp = self.client.post("/api/agent", json={"question": "merhaba"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["answer"], "cevap")

    def test_an_empty_question_is_rejected(self):
        resp = self.client.post("/api/agent", json={"question": "  "})
        self.assertEqual(resp.status_code, 400)

    def test_a_question_over_4000_characters_is_rejected(self):
        with fake_urlopen({"choices": [{"message": {"content": "cevap"}}]}):
            resp = self.client.post("/api/agent", json={"question": "a" * 4001})
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
                                json={"settings": {"cleanup_prompt": "some/prompt"}})
        self.assertEqual(post.status_code, 200)
        self.assertEqual(cfg.Config()["cleanup_prompt"], "some/prompt")

if __name__ == "__main__":
    unittest.main()
