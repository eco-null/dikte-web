"""The model/download catalogue hub: GitHub + Hugging Face, cached."""

import unittest

import hub
from tests.support import DikteTest, fake_urlopen, url_error


class Hub(DikteTest):
    def setUp(self):
        super().setUp()
        self.patch_attr(hub, "CACHE_DIR", self.path("cache"))

    def test_release_parses_assets(self):
        payload = {"tag_name": "b3340",
                   "assets": [{"name": "bin-ubuntu-x64.tar.gz",
                               "browser_download_url": "https://x/b.tgz",
                               "size": 123, "digest": "sha256:abcdef"}]}
        with fake_urlopen(payload):
            tag, items = hub.release("ggml-org/whisper.cpp")
        self.assertEqual(tag, "b3340")
        self.assertEqual(items[0].name, "bin-ubuntu-x64.tar.gz")
        self.assertEqual(items[0].sha256, "abcdef")
        self.assertEqual(items[0].size, 123)

    def test_files_parses_lfs_entries(self):
        payload = [{"path": "ggml-small.bin", "type": "file",
                    "lfs": {"size": 50, "oid": "sha256:1234"},
                    "downloadUrl": "https://hf/x"}]
        with fake_urlopen(payload):
            items = hub.files("ggerganov/whisper.cpp")
        self.assertEqual(items[0].name, "ggml-small.bin")
        self.assertEqual(items[0].sha256, "1234")

    def test_repos_parses_list(self):
        payload = [{"id": "ggml-org/gemma-3-4b-it-GGUF",
                    "downloads": 10, "updatedAt": "2025-01-01"}]
        with fake_urlopen(payload):
            repos = hub.repos(author="ggml-org")
        self.assertEqual(repos[0].id, "ggml-org/gemma-3-4b-it-GGUF")

    def test_network_failure_raises_hub_error(self):
        with fake_urlopen(url_error()):
            with self.assertRaises(hub.HubError):
                hub.release("x/y")

    def test_cache_is_used_on_second_call(self):
        payload = {"tag_name": "b1",
                   "assets": [{"name": "x", "size": 1,
                               "browser_download_url": "https://x/x"}]}
        with fake_urlopen(payload, url_error()):
            hub.release("a/b", refresh=True)
            hub.release("a/b")  # served from cache; a 2nd network hit would raise
        self.assertEqual(hub._read_cache("gh-a/b-latest", 999), payload)


if __name__ == "__main__":
    unittest.main()
