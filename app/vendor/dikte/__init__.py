"""Vendored dikte çekirdeği.

Modüller birbirini bare-name ile import eder; sys.modules'a kaydedilince
`import api`, `import config as cfg` her yerde çalışır. Liste, her modül
de-Qt edildikçe genişletilir (worker, filetranscribe, meeting, assistant,
cleanup; T3–T7).
"""
import importlib
import sys

_MODULES = ("i18n", "hub", "ggml", "vad", "api", "config", "assistant",
            "cleanup", "filetranscribe", "meeting", "worker")

for _name in _MODULES:
    sys.modules[_name] = importlib.import_module(f"{__name__}.{_name}")
