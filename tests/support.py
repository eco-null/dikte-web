

import array
import contextlib
import io
import json
import math
import os
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
import wave
from unittest import mock

import assistant
import config as cfg
import i18n

def _no_network(*args, **kwargs):
    raise AssertionError(
        "a test reached the network; wrap the call in support.fake_urlopen"
    )

class DikteTest(unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.root = tempfile.mkdtemp(prefix="dikte-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

        config_dir = self.path("config", "dikte")
        data_dir = self.path("data", "dikte")
        self.patch_paths(
            CONFIG_DIR=config_dir,
            CONFIG_FILE=config_dir / "config.json",
            DATA_DIR=data_dir,
            HISTORY_FILE=data_dir / "history.jsonl",
            RECORDINGS_DIR=data_dir / "recordings",
            MEETINGS_DIR=data_dir / "meetings",
            MEETINGS_FILE=data_dir / "meetings.jsonl",
        )
        self.patch_attr(assistant, "SESSION_FILE", data_dir / "assistant.json")

        i18n.set_language("en")
        self.addCleanup(i18n.set_language, "en")

        self.patch_attr(urllib.request, "urlopen", _no_network)

    def path(self, *parts):

        import pathlib
        return pathlib.Path(self.root, *parts)

    def patch_paths(self, **paths):
        patcher = mock.patch.multiple(cfg, **paths)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_attr(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def config(self, **values):

        conf = cfg.Config()
        for key, value in values.items():
            conf[key] = value
        return conf

    def write_config(self, payload):

        cfg.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cfg.CONFIG_FILE.write_text(json.dumps(payload), encoding="utf-8")

    def read_config_file(self):
        return json.loads(cfg.CONFIG_FILE.read_text(encoding="utf-8"))

def json_body(payload):

    body = json.dumps(payload).encode("utf-8")
    resp = mock.MagicMock()
    resp.read.return_value = body
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp

def raw_body(text):

    resp = mock.MagicMock()
    resp.read.return_value = text.encode("utf-8")
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp

def http_error(code, body=""):
    return urllib.error.HTTPError(
        "https://example.invalid/v1", code, "boom", {},
        io.BytesIO(body.encode("utf-8")),
    )

def url_error(reason="no route to host"):
    return urllib.error.URLError(reason)

@contextlib.contextmanager
def fake_urlopen(*replies):

    calls = []

    def opener(req, timeout=None):
        calls.append(req)
        reply = replies[min(len(calls) - 1, len(replies) - 1)] if replies else {}
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, (dict, list)):
            return json_body(reply)
        return reply

    try:
        with mock.patch("urllib.request.urlopen", side_effect=opener):
            yield calls
    finally:
        for reply in replies:
            if isinstance(reply, urllib.error.HTTPError):
                reply.close()

def sent_json(request):

    return json.loads(request.data.decode("utf-8"))

def multipart_fields(request):

    body = request.data.decode("utf-8", "replace")
    fields = {}
    for part in body.split("\r\n--"):
        if 'name="' not in part or "filename=" in part:
            continue
        name = part.split('name="', 1)[1].split('"', 1)[0]
        _, _, value = part.partition("\r\n\r\n")
        fields[name] = value.rstrip("\r\n")
    return fields

def pcm(samples):
    return array.array("h", samples).tobytes()

def tone(seconds, rate=16000, amplitude=8000, channels=1, freq=440.0):

    frames = int(seconds * rate)
    out = array.array("h")
    for index in range(frames):
        value = int(amplitude * math.sin(2 * math.pi * freq * index / rate))
        out.extend([value] * channels)
    return out.tobytes()

def silence(seconds, rate=16000, channels=1):
    return b"\x00\x00" * int(seconds * rate) * channels

def speech(seconds, rate=16000, amplitude=16000, freq=440.0):

    half = seconds / 2
    return silence(half, rate) + tone(half, rate, amplitude, freq=freq)

def make_wav(path, data, rate=16000, channels=1, width=2):
    os.makedirs(os.path.dirname(str(path)) or ".", exist_ok=True)
    with contextlib.closing(wave.open(str(path), "wb")) as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(width)
        wav.setframerate(rate)
        wav.writeframes(data)
    return str(path)

def stereo(left, right):

    a, b = array.array("h"), array.array("h")
    a.frombytes(left)
    b.frombytes(right)
    out = array.array("h")
    for first, second in zip(a, b):
        out.extend((first, second))
    return out.tobytes()

class FakeCompleted:

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def only_these_tools(*names):

    wanted = set(names)
    return mock.patch("shutil.which", side_effect=lambda tool: (
        f"/usr/bin/{tool}" if tool in wanted else None))
