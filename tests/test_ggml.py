

import hashlib
import socket
import unittest
from unittest import mock

import ggml
import hub
from tests.support import DikteTest, fake_urlopen

def _binary_ok(body):

    resp = mock.MagicMock()
    resp.headers = {"Content-Length": str(len(body))}
    resp.read.side_effect = [body] + [b""] * 20
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return mock.patch("urllib.request.urlopen", return_value=resp)

class GgmlDownload(DikteTest):
    def setUp(self):
        super().setUp()
        self.patch_attr(ggml, "DATA_DIR", self.path("data"))
        self.patch_attr(ggml, "BIN_DIR", self.path("data", "bin"))
        self.patch_attr(ggml, "MODELS_DIR", self.path("data", "models"))

    def test_human_size(self):
        self.assertEqual(ggml.human_size(500), "500 B")
        self.assertEqual(ggml.human_size(2048), "2.0 KB")
        self.assertEqual(ggml.human_size(5 << 20), "5.0 MB")

    def test_arch_is_arm64_or_x64(self):
        self.assertIn(ggml._arch(), ("arm64", "x64"))

    def test_download_without_checksum_is_refused(self):
        item = hub.Item("m.bin", "https://x/m.bin", 10, "")
        with self.assertRaises(ggml.LocalError):
            ggml.download(item, str(self.path("m.bin")))

    def test_download_writes_and_verifies(self):
        body = b"hello world"
        item = hub.Item("m.bin", "https://x/m.bin", len(body),
                        hashlib.sha256(body).hexdigest())
        with _binary_ok(body):
            ok = ggml.download(item, str(self.path("m.bin")))
        self.assertTrue(ok)
        self.assertEqual(self.path("m.bin").read_bytes(), body)

    def test_download_reports_progress(self):
        body = b"a" * 3000
        item = hub.Item("m.bin", "https://x/m.bin", len(body),
                        hashlib.sha256(body).hexdigest())
        seen = []
        with _binary_ok(body):
            ggml.download(item, str(self.path("m.bin")),
                          on_progress=lambda done, total: seen.append((done, total)))
        self.assertGreater(len(seen), 0)
        self.assertEqual(seen[-1][0], len(body))

    def test_download_checksum_mismatch_raises(self):
        item = hub.Item("m.bin", "https://x/m.bin", 5, "0" * 64)
        with _binary_ok(b"12345"):
            with self.assertRaises(ggml.LocalError):
                ggml.download(item, str(self.path("m.bin")))

    def test_download_refuses_when_stopped(self):
        item = hub.Item("m.bin", "https://x/m.bin", 100, "0" * 64)
        with _binary_ok(b"x" * 50):
            ok = ggml.download(item, str(self.path("m.bin")),
                               should_stop=lambda: True)
        self.assertFalse(ok)
        self.assertFalse(self.path("m.bin").exists())

def _files_reply(items):

    import json
    body = [{"type": "file", "path": it.name,
             "lfs": {"size": it.size, "oid": "sha256:" + it.sha256},
             "downloadUrl": it.url} for it in items]
    return fake_urlopen(json.loads(json.dumps(body)))

class GgmlCatalog(DikteTest):
    def setUp(self):
        super().setUp()
        self.patch_attr(ggml, "DATA_DIR", self.path("data"))
        self.patch_attr(ggml, "BIN_DIR", self.path("data", "bin"))
        self.patch_attr(ggml, "MODELS_DIR", self.path("data", "models"))
        self.patch_attr(hub, "CACHE_DIR", self.path("cache"))

    def test_whisper_models_filters_and_sorts(self):
        files = [hub.Item(f"ggml-{n}.bin", f"https://x/{n}", size, "a")
                 for n, size in (("large", 900), ("small", 100), ("tiny", 10))]
        files.append(hub.Item("README.md", "https://x/r", 5, "a"))
        with _files_reply(files):
            models = ggml.whisper_models()
        self.assertEqual([m.name for m in models],
                         ["ggml-tiny.bin", "ggml-small.bin", "ggml-large.bin"])

    def test_llm_quants_skips_multipart_and_oversized(self):
        big = hub.Item("big.gguf", "https://x/b", (16 << 30) + 1, "a")
        split = hub.Item("m-of-00002.gguf", "https://x/s", 100, "a")
        good = hub.Item("m.gguf", "https://x/m", 200, "a")
        with _files_reply([big, split, good]):
            quants = ggml.llm_quants("ggml-org/gemma-3-4b-it-GGUF")
        self.assertEqual([q.name for q in quants], ["m.gguf"])

    def test_whisper_model_path_stays_inside_the_models_dir(self):

        path = ggml.whisper_model_path("../../evil.bin")
        self.assertEqual(path, ggml.MODELS_DIR / "whisper" / "evil.bin")
        self.assertTrue(path.is_relative_to(ggml.MODELS_DIR))
        self.assertEqual(ggml.llm_model_path("repo/../../other.gguf"),
                         ggml.MODELS_DIR / "llm" / "other.gguf")

    def test_installed_whisper_models(self):
        d = ggml.MODELS_DIR / "whisper"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ggml-a.bin").write_bytes(b"x")
        (d / "ggml-b.bin").write_bytes(b"x")
        (d / "junk.txt").write_text("x")
        self.assertEqual(ggml.installed_whisper_models(),
                         ["ggml-a.bin", "ggml-b.bin"])

    def test_delete_model(self):
        p = self.path("data", "models", "whisper", "ggml-x.bin")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        ggml.delete_model(str(p))
        self.assertFalse(p.exists())
        ggml.delete_model(str(p))

    def test_free_port_is_listenable(self):
        port = ggml._free_port()
        self.assertFalse(ggml._listening(port))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((ggml.HOST, port))

class GgmlServer(DikteTest):
    def setUp(self):
        super().setUp()
        self.patch_attr(ggml, "DATA_DIR", self.path("data"))
        self.patch_attr(ggml, "BIN_DIR", self.path("data", "bin"))
        self.patch_attr(ggml, "MODELS_DIR", self.path("data", "models"))
        ggml.stop_all()
        self.addCleanup(ggml.stop_all)

    def test_server_configure_and_settings(self):
        ggml.whisper.configure(model="ggml-small.bin")
        self.assertEqual(ggml.whisper.settings()["model"], "ggml-small.bin")

    def test_server_serve_returns_url_when_running(self):
        proc = mock.MagicMock()
        proc.poll.return_value = None
        ggml.whisper._proc = proc
        ggml.whisper._port = 12345
        ggml.whisper._key = ggml.whisper._settings_key()
        self.assertEqual(ggml.whisper.serve(), "http://127.0.0.1:12345/v1")

    def test_stop_all_clears_servers(self):
        ggml.whisper._proc = mock.MagicMock()
        ggml.whisper._port = 1
        ggml.stop_all()
        self.assertIsNone(ggml.whisper._proc)

if __name__ == "__main__":
    unittest.main()
