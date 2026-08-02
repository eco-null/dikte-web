"""Yerel whisper.cpp/llama.cpp modülünün stub'ı.

Webapp yalnızca hosted API kullanır. config.DEFAULTS import anında ggml
sabitlerini okur, o yüzden modülün adı ve sabitleri var; gerçek kullanım
LocalError ile reddedilir.
"""


class LocalError(Exception):
    pass


class _Unavailable:
    def __init__(self, name):
        self._name = name

    def __getattr__(self, name):
        def missing(*args, **kwargs):
            raise LocalError(
                f"{self._name}.{name}: local models are not available "
                "in the webapp (hosted providers only)")
        return missing


SUGGESTED_WHISPER = ""
SUGGESTED_LLM = ("",)
WHISPER = "whisper.cpp"
LLAMA = "llama.cpp"
MODELS_DIR = None

whisper = _Unavailable("whisper")
llm = _Unavailable("llm")


def program_path(server, binary=""):
    return ""


def have_model(path):
    return False


def whisper_model_path(name):
    import pathlib
    return pathlib.Path("/nonexistent") / name


def llm_model_path(name):
    import pathlib
    return pathlib.Path("/nonexistent") / name
