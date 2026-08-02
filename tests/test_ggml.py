"""ggml: downloads, installs, and runs whisper.cpp / llama.cpp."""

import hashlib
import unittest
from unittest import mock

import ggml
import hub
from tests.support import DikteTest, fake_urlopen


def _binary_ok(body):
    """A urlopen stand-in that streams `body` with a Content-Length header."""
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


if __name__ == "__main__":
    unittest.main()
