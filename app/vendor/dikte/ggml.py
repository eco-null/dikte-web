"""Speech to text and cleanup on this machine: whisper.cpp and llama.cpp.

Two programs, one treatment. Fetch a release from GitHub, unpack it under the
data directory, fetch a model from Hugging Face, then keep one server alive on a
port of its own. Both of them speak the shape api.py already sends to the hosted
providers, so what the rest of Dikte sees is a base URL and nothing else:
whisper-server is started on `--inference-path /v1/audio/transcriptions`, the
exact path api.py builds, and llama-server answers /v1/chat/completions the way
OpenRouter does.

A server rather than a one-shot run, because the model is the slow part. Loading
a large whisper model takes a second or two while transcribing a few seconds of
speech takes a fraction of one, and an LLM is worse: a server pays that once and
a run per dictation pays it every time.

Nothing downloaded is trusted for having arrived. Every file is checked against
the sha256 its index published, and the bytes go to a `.part` that is only
renamed once the whole thing is there, so an interrupted download can never be
mistaken for a working one.

This module imports hub and the string table, and nothing else of Dikte's: it
knows how to fetch a file and how to run a process, and nothing about dictation.
Its errors leave as LocalError and api.py turns them into the ApiError the
interface already knows how to show.
"""

import collections
import ctypes.util
import hashlib
import http.client
import json
import os
import pathlib
import platform
import shutil
import socket
import tarfile
import threading
import urllib.error
import urllib.request

import hub
from i18n import t

HOST = "127.0.0.1"
# The path api.py asks for, so its URL and the server's line up.
INFERENCE_PATH = "/v1/audio/transcriptions"

DATA_DIR = (pathlib.Path(os.environ.get("XDG_DATA_HOME")
                         or os.path.expanduser("~/.local/share")) / "dikte")
BIN_DIR = DATA_DIR / "bin"
MODELS_DIR = DATA_DIR / "models"

# Loading a large model onto a GPU is the slow part of a start, and on a cold
# page cache a large LLM read from a spinning disk is slower still.
STARTUP_TIMEOUT = 180.0
DOWNLOAD_CHUNK = 1 << 20

# `health` is the path that answers only once the model is in memory. whisper
# does not have one and does not need one: it binds its port after the model is
# loaded, so the port opening is the signal.
Program = collections.namedtuple("Program", "name repo binary health")

WHISPER = Program("whisper", "ggml-org/whisper.cpp", "whisper-server", "")
LLAMA = Program("llama", "ggml-org/llama.cpp", "llama-server", "/health")

# Where the models are listed. Neither list is written into Dikte: a catalogue
# in the source means a release of Dikte for every model somebody else
# publishes.
WHISPER_MODELS_REPO = "ggerganov/whisper.cpp"
LLM_AUTHOR = "ggml-org"

# What the whisper repository holds besides models: Core ML encoders for Apple
# hardware and the odd loose file.
WHISPER_PREFIX = "ggml-"
WHISPER_SUFFIX = ".bin"

# What a GGUF repository holds besides the model: mmproj is the vision half of a
# multimodal model, mtp a draft head for speculative decoding. Neither is a model
# a server can be started on, and offering them is offering a failure.
GGUF_SKIP = ("mmproj", "mtp-")
# Big enough for a 12B at Q4 and far past anything cleanup wants; the point is
# to keep a 400 GB frontier model out of a list somebody might click.
GGUF_MAX_BYTES = 16 << 30

# Suggestions, not a catalogue: the list itself is fetched, and these are only
# the rows that float to the top of it. Small instruction-following models,
# because cleanup is punctuation and filler words rather than anything that
# wants thinking about.
SUGGESTED_LLM = (
    "ggml-org/gemma-3-4b-it-GGUF",
    "ggml-org/gemma-4-E2B-it-GGUF",
    "ggml-org/gemma-4-E4B-it-GGUF",
    "ggml-org/SmolLM3-3B-GGUF",
)
# Turbo at q5_0 is smaller than `small` and better than it, which makes the
# usual "start small" advice point at the same file as "start good".
SUGGESTED_WHISPER = "ggml-large-v3-turbo-q5_0.bin"


class LocalError(Exception):
    pass


def human_size(count):
    for unit in ("B", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return f"{count:.0f} {unit}" if unit == "B" else f"{count:.1f} {unit}"
        count /= 1024.0
    return f"{count:.1f} GB"


# --- fetching -------------------------------------------------------------


def download(item, target, on_progress=None, should_stop=None, require_hash=True):
    """Fetch one hub.Item to `target`. True when it landed, False when stopped.

    The bytes go to a `.part` that is renamed only after both the length and the
    hash agree with what the index said. A truncated file would otherwise sit
    there looking installed and fail much later, inside a server, as a corrupt
    model; a file that is the right length but the wrong content is worse, and
    this is a program as often as it is a model.

    A file whose index published no hash is refused rather than taken on trust.
    Everything fetched here is either run or parsed by something written in C++,
    and GitHub did not always publish a digest: a release old enough to predate
    that would otherwise install unchecked, which is the one case where this
    would matter most and say least.
    """
    target = pathlib.Path(target)
    if require_hash and not item.sha256:
        raise LocalError(t("{name} is published without a checksum, so there is "
                           "no way to tell what arrived. Nothing was installed.",
                           name=item.name))
    part = target.with_name(target.name + ".part")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise LocalError(t("Could not create {path}: {error}",
                           path=target.parent, error=exc)) from exc

    request = urllib.request.Request(item.url, headers={"User-Agent": hub.USER_AGENT})
    digest = hashlib.sha256()
    done = 0
    stopped = False
    too_long = False
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or item.size or 0)
            with open(part, "wb") as out:
                while True:
                    if should_stop is not None and should_stop():
                        stopped = True
                        break
                    block = response.read(DOWNLOAD_CHUNK)
                    if not block:
                        break
                    out.write(block)
                    digest.update(block)
                    done += len(block)
                    # More than was announced: a body that does not end is the
                    # one way this loop could run until the disk is full.
                    if total and done > total:
                        too_long = True
                        break
                    if on_progress is not None:
                        on_progress(done, total)
        # The `.part` file is closed by now; it has to be before it is removed,
        # because the platforms this runs on refuse to unlink an open file.
        if stopped:
            part.unlink(missing_ok=True)
            return False
        if too_long:
            part.unlink(missing_ok=True)
            raise LocalError(t("{name} is longer than it said it "
                               "would be.", name=item.name))
        # A proxy notice or an error page that came back as 200 would otherwise
        # be renamed into place and only fail when something tries to read it.
        if total and done != total:
            part.unlink(missing_ok=True)
            raise LocalError(t("The download stopped early ({done} of {total}).",
                               done=human_size(done), total=human_size(total)))
        if item.sha256 and digest.hexdigest() != item.sha256:
            part.unlink(missing_ok=True)
            raise LocalError(t("{name} does not match its published checksum. "
                               "Nothing was installed.", name=item.name))
        part.replace(target)
        return True
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        exc.close()   # it holds the response body open until it is collected
        raise LocalError(t("Could not download {name}: HTTP {code}",
                           name=item.name, code=exc.code)) from exc
    except urllib.error.URLError as exc:
        part.unlink(missing_ok=True)
        raise LocalError(t("Could not download {name}: {error}",
                           name=item.name, error=exc.reason)) from exc
    except OSError as exc:
        # A connection cut mid-body arrives here too, and gigabytes in is
        # exactly where that happens.
        part.unlink(missing_ok=True)
        raise LocalError(t("Could not write {name}: {error}",
                           name=item.name, error=exc)) from exc


# --- the programs ---------------------------------------------------------


def _arch():
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "arm64"
    return "x64"


def _has_vulkan():
    """Whether a Vulkan loader is installed, which decides which build to fetch.

    llama.cpp publishes no CUDA build for Linux, so Vulkan is what a graphics
    card gets here. The build without it is smaller and runs on the CPU, and
    fetching the Vulkan one for a machine that cannot load it would only make
    the download bigger.
    """
    return bool(ctypes.util.find_library("vulkan"))


def _wanted_assets(program):
    """Asset name endings to accept, best first."""
    arch = _arch()
    if program is LLAMA and _has_vulkan():
        return (f"bin-ubuntu-vulkan-{arch}.tar.gz", f"bin-ubuntu-{arch}.tar.gz")
    return (f"bin-ubuntu-{arch}.tar.gz",)


def _install_record(program):
    return BIN_DIR / program.name / "installed.json"


def installed_program(program):
    """The binary Dikte downloaded, or "" when there is none that still runs."""
    try:
        record = json.loads(_install_record(program).read_text(encoding="utf-8"))
        path = record.get("binary") or ""
    except (OSError, ValueError):
        return ""
    return path if os.path.isfile(path) and os.access(path, os.X_OK) else ""


def installed_version(program):
    try:
        record = json.loads(_install_record(program).read_text(encoding="utf-8"))
        return record.get("tag") or ""
    except (OSError, ValueError):
        return ""


def program_path(program, custom=""):
    """Which copy of the program to run, or "" when there is none.

    A system one wins over a downloaded one. The distribution package is built
    against whatever the machine has, which on this platform means it may reach
    the graphics card, while the release binaries carry CPU backends only.
    """
    custom = (custom or "").strip()
    if custom:
        return custom if os.path.isfile(custom) and os.access(custom, os.X_OK) else ""
    return shutil.which(program.binary) or installed_program(program)


def system_program(program):
    """Whether the program came from the system rather than from Dikte."""
    return bool(shutil.which(program.binary))


def _find_binary(root, name):
    for path in sorted(pathlib.Path(root).rglob(name)):
        if path.is_file():
            return path
    return None


def _extract(archive, into):
    """Unpack a release tarball, refusing anything that reaches outside `into`.

    The archives lay their libraries next to their binaries and are linked with
    an $ORIGIN runpath, so a whole directory is what has to survive the trip and
    the binary cannot be lifted out of it.
    """
    try:
        with tarfile.open(archive, "r:gz") as tar:
            try:
                tar.extractall(into, filter="data")
            except TypeError:      # Python without the extraction filters
                tar.extractall(into)
    except (tarfile.TarError, OSError) as exc:
        raise LocalError(t("Could not unpack {name}: {error}",
                           name=os.path.basename(str(archive)), error=exc)) from exc


def install_program(program, tag="", on_progress=None, should_stop=None,
                    refresh=False):
    """Fetch and unpack a release. The path to the binary, or "" when stopped.

    `tag` is empty for whatever the project released last, which is the point:
    a version pinned in Dikte's source would mean a release of Dikte every time
    whisper.cpp has one.
    """
    try:
        tag, assets = hub.release(program.repo, tag or "latest", refresh=refresh)
    except hub.HubError as exc:
        raise LocalError(str(exc)) from exc

    item = None
    for ending in _wanted_assets(program):
        item = next((a for a in assets if a.name.endswith(ending)), None)
        if item:
            break
    if item is None:
        raise LocalError(t("{repo} {tag} has no build for this machine.",
                           repo=program.repo, tag=tag))

    into = BIN_DIR / program.name / tag
    shutil.rmtree(into, ignore_errors=True)
    archive = BIN_DIR / program.name / item.name
    try:
        if not download(item, archive, on_progress, should_stop):
            return ""
        _extract(archive, into)
        binary = _find_binary(into, program.binary)
        if binary is None:
            raise LocalError(t("{name} was not in the download.",
                               name=program.binary))
        binary.chmod(binary.stat().st_mode | 0o111)
        _install_record(program).write_text(
            json.dumps({"tag": tag, "binary": str(binary)}), encoding="utf-8")
    except OSError as exc:
        raise LocalError(t("Could not install {name}: {error}",
                           name=program.name, error=exc)) from exc
    finally:
        try:
            archive.unlink(missing_ok=True)
        except OSError:
            pass
    _drop_old_versions(program, keep=tag)
    return str(binary)


def _drop_old_versions(program, keep):
    """Leave one unpacked release behind, not one per update."""
    root = BIN_DIR / program.name
    try:
        for path in root.iterdir():
            if path.is_dir() and path.name != keep:
                shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass
