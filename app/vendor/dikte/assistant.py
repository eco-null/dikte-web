"""Ajan'a soru sormak ve cevabı geri döndürmek. (webapp)

Beş sağlayıcı: openai, groq, openrouter, omniroute ve yerel llama.cpp (local).
Masaüstünün Claude/Codex CLI yolları webapp'e taşınmaz.
"""

import json
import time

import api
import config as cfg
from i18n import t

SESSION_FILE = cfg.DATA_DIR / "assistant.json"
PROVIDERS = ("openai", "groq", "openrouter", "omniroute", "local")
MAX_HISTORY = 24


class AssistantError(Exception):
    pass


class Cancelled(Exception):
    pass


def provider(conf):
    chosen = conf["assistant_provider"]
    return chosen if chosen in PROVIDERS else "openrouter"


def display_name(conf):
    return {"openai": "OpenAI", "groq": "Groq", "openrouter": "OpenRouter",
            "omniroute": "OmniRoute", "local": "Local llama.cpp"}.get(
                provider(conf), provider(conf))


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
    return _ask_http(prompt, conf, name, on_stage)


def _ask_http(prompt, conf, name, on_stage):
    if on_stage:
        on_stage(t("Thinking…"))
    history = read_messages(name, conf["assistant_session_minutes"] * 60)
    messages = history + [{"role": "user", "content": prompt}]
    key = conf[f"assistant_{name}_key"]
    base_url = conf[f"assistant_{name}_url"]
    model = conf[f"assistant_{name}_model"]
    api._assert_safe_url(base_url)
    service = {"openai": "OpenAI", "groq": "Groq",
               "openrouter": "OpenRouter", "omniroute": "OmniRoute",
               "local": "Local llama.cpp"}.get(name, name)
    key_required = name not in ("omniroute", "local")
    try:
        answer = api.chat(
            messages, key, model=model, system_prompt=conf.assistant_prompt(),
            reasoning=conf["assistant_reasoning"], base_url=base_url,
            timeout=conf["assistant_timeout"], provider=name,
            service=service, key_required=key_required,
        )
    except api.ApiError as exc:
        raise AssistantError(str(exc)) from exc
    write_session(name, messages=messages + [{"role": "assistant", "content": answer}])
    return answer, ""
