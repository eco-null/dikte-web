"""Ajan'a soru sormak ve cevabı geri döndürmek. (webapp)

İki provider, ikisi de HTTP: OpenRouter (yapılandırılmış anahtar üzerinden
chat) ve OmniRoute (OpenAI-uyumlu yerel uç). Masaüstünün Claude/Codex CLI
yolları webapp'e taşınmaz.
"""

import json
import os
import time

import api
import config as cfg
from i18n import t

SESSION_FILE = cfg.DATA_DIR / "assistant.json"
PROVIDERS = ("openrouter", "omniroute")
MAX_HISTORY = 24


class AssistantError(Exception):
    pass


class Cancelled(Exception):
    pass


def provider(conf):
    chosen = conf["assistant_provider"]
    return chosen if chosen in PROVIDERS else "openrouter"


def display_name(conf):
    return "OmniRoute" if provider(conf) == "omniroute" else "OpenRouter"


# --- the conversation (orijinalden aynen) --------------------------------

def _read_row(name, max_age_seconds):
    try:
        with open(SESSION_FILE, encoding="utf-8") as fh:
            row = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    if not isinstance(row, dict) or row.get("provider") != name:
        return {}
    if max_age_seconds and time.time() - row.get("ts", 0) > max_age_seconds:
        return {}
    return row


def read_session(name, max_age_seconds):
    return str(_read_row(name, max_age_seconds).get("session", ""))


def read_messages(name, max_age_seconds):
    messages = _read_row(name, max_age_seconds).get("messages")
    return messages if isinstance(messages, list) else []


def write_session(name, session="", messages=None):
    row = {"provider": name, "session": session, "ts": time.time()}
    if messages is not None:
        row["messages"] = messages[-MAX_HISTORY:]
    try:
        cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as fh:
            json.dump(row, fh, ensure_ascii=False)
    except OSError:
        pass


def clear_session():
    try:
        SESSION_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def stored_provider():
    try:
        with open(SESSION_FILE, encoding="utf-8") as fh:
            row = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return ""
    return str(row.get("provider", "")) if isinstance(row, dict) else ""


def session_age():
    try:
        with open(SESSION_FILE, encoding="utf-8") as fh:
            row = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(row, dict) or not (row.get("session") or row.get("messages")):
        return None
    return time.time() - row.get("ts", 0)


# --- the call ------------------------------------------------------------

def ask(prompt, conf, on_stage=None, should_stop=None, provider="", model=""):
    """Soruyu yapılandırılmış ajandan geçirir; (answer, warning) döndürür."""
    name = provider or conf["assistant_provider"]
    if name not in PROVIDERS:
        name = "openrouter"
    if name == "omniroute":
        base_url = os.environ.get("OMNIROUTE_BASE_URL") or conf["assistant_omniroute_base_url"]
        return _ask_http(prompt, conf, "omniroute", base_url,
                         model or conf["assistant_omniroute_model"], on_stage)
    return _ask_http(prompt, conf, "openrouter", conf["openrouter_base_url"],
                     model or conf["assistant_openrouter_model"], on_stage)


def _ask_http(prompt, conf, name, base_url, model, on_stage):
    if on_stage:
        on_stage(t("Thinking…"))
    history = read_messages(name, conf["assistant_session_minutes"] * 60)
    messages = history + [{"role": "user", "content": prompt}]
    try:
        answer = api.chat(
            messages, conf.openrouter_key(), model, conf.assistant_prompt(),
            reasoning=conf["assistant_reasoning"], base_url=base_url,
            timeout=conf["assistant_timeout"], provider=name,
            service="OmniRoute" if name == "omniroute" else "OpenRouter",
            key_required=(name == "openrouter"),
        )
    except api.ApiError as exc:
        raise AssistantError(str(exc)) from exc
    write_session(name, messages=messages + [{"role": "assistant", "content": answer}])
    return answer, ""
