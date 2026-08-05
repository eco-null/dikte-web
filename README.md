# Dikte Web

> **[Türkçe okuyun](README.tr.md)** · [Read in Turkish](README.tr.md)

<p align="center">
  <img src="app/static/logo.png" alt="Dikte Web" width="120">
</p>

**Dikte Web** is a single-user, self-hosted speech-to-text web app. It is a web
rewrite of [yusufipk/dikte](https://github.com/yusufipk/dikte) — a voice
dictation app for Linux — that drops the Qt desktop shell and serves the same
transcription engine through a **FastAPI + HTMX** interface you use in a
browser.

This repository is a **fork** of
[yusufipk/dikte](https://github.com/yusufipk/dikte). The core transcription
engine, VAD, cleanup prompts, meeting pipeline and agent logic are derived from
the original project; the Qt desktop UI is replaced here with a web UI. The
original desktop codebase is preserved on the `upstream-dikte` branch.

---

## Features

- **Dictation** — record your voice in the browser and get a transcript, with
  optional AI cleanup that removes fillers ("uh", "um"), stutters and thinking
  sounds, adds punctuation, and repairs words the transcriber misheard.
- **File transcription** — upload an audio or video file (mp3, m4a, mp4, wav,
  …) and download the result as plain text or **SRT subtitles**.
- **Meeting minutes** — upload a mono or stereo recording; the app transcribes
  it, separates the speakers (you / the other side), and writes **markdown
  minutes** with a summary.
- **Agent** — ask a question and get an answer from a configurable assistant
  model, with conversation history.
- **History** — every dictation is saved to a searchable list you can clear.
- **Settings** — all transcription, cleanup, meeting and assistant options live
  in the web UI. API keys are masked and only ever replaced, never shown.

## Interface

- **Modern dark interface** — teal/orange accent palette and Inter typography.
- **Keyboard navigation** — every control has a visible focus ring; the UI
  also honors `prefers-reduced-motion`, toning down animations for users who
  ask for it.
- **Sectioned Settings** — transcription, cleanup, local models, meetings and
  assistant options are grouped into sections, plus a **Models** manager for
  installing the whisper.cpp / llama.cpp binaries and model files right from
  the UI.

## Language support

The interface ships in **English and Turkish**. Set `ui_language` to `auto`,
`en` or `tr` in Settings; `auto` guesses from your locale. The cleanup and
meeting prompts are language-specific too.

## Transcription providers

Any of these can be selected in Settings as the transcription provider:

| Provider | Base URL | Model default |
|----------|----------|---------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-transcribe` |
| Groq | `https://api.groq.com/openai/v1` | `whisper-large-v3-turbo` |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o-transcribe` |
| Local (whisper.cpp) | none (runs on this machine) | whisper `.bin` model (installed via Settings → Models) |

The assistant (agent) supports **OpenRouter** (cloud) and **OmniRoute** (a
local, OpenAI-compatible endpoint), the latter intended for machines on your
own network, e.g. a local LLM server.

---

## Quick start (Docker)

1. Create a `.env` file in the project directory:

   ```dotenv
   DIKTE_WEB_PASSWORD=your-password
   OPENAI_API_KEY=sk-...            # optional
   GROQ_API_KEY=...                 # optional
   OPENROUTER_API_KEY=...           # optional
   OMNIROUTE_BASE_URL=http://host.docker.internal:20128/v1   # optional
   ```

   The API keys are only needed for the providers you actually use. Values are
   optional; if `DIKTE_WEB_PASSWORD` is left empty the app generates one and
   stores it in the data volume.

2. Start the app:

   ```bash
   docker compose up -d
   ```

3. Open http://localhost:8000 and log in with the password.

The image installs **ffmpeg**, so any audio/video conversion works out of the
box. Uploads are capped at 1 GB (`DIKTE_MAX_UPLOAD`).

> **Exposure:** `docker-compose.yml` binds the service to **loopback only**
> (`127.0.0.1:8000`). It is not reachable from outside the host until you put
> something in front of it. Two options below.

### Expose it with a Cloudflare Tunnel (no reverse proxy needed)

If you have a domain on Cloudflare, `cloudflared` terminates TLS at
Cloudflare's edge and tunnels to the loopback port — no reverse proxy to run:

1. Install `cloudflared` on the host (see
   [developers.cloudflare.com](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)).
2. Log in and create a tunnel (one-time):
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create dikte-web
   ```
3. Configure `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: dikte-web
   credentials-file: /home/USER/.cloudflared/USERID.json

   ingress:
     - hostname: dikte.example.com
       service: http://localhost:8000
     - service: http_status:404
   ```
4. Route the DNS name to the tunnel, then run it (as a systemd service for
   persistence):
   ```bash
   cloudflared tunnel route dns dikte-web dikte.example.com
   cloudflared tunnel run dikte-web
   ```
5. Open `https://dikte.example.com` and log in.

The app already trusts Cloudflare's `CF-Connecting-IP` header for login rate
limiting, so each real visitor gets their own attempt budget. Keep
`DIKTE_COOKIE_SECURE=1` (the default) — Cloudflare serves HTTPS, so the
`Secure` cookie works. Do **not** expose port 8000 to the internet in addition;
the tunnel is the only entry point.

### The OmniRoute default

`host.docker.internal` resolves to the Docker host machine (compose maps it
with `host-gateway`). If you run a local LLM server on the host at port 20128,
the agent works immediately.

**Settings** (page → *Assistant* section), three fields:

| Field | Purpose |
|-------|---------|
| `assistant_provider` | choose **OmniRoute** |
| `assistant_omniroute_base_url` | the endpoint, e.g. `http://host.docker.internal:20128/v1` |
| `assistant_omniroute_model` | the model id (e.g. `gemma-3-4b-it`) |
| `assistant_omniroute_api_key` | **optional** — sent as a `Bearer` token when set; left empty for keyless local endpoints |

You can also override the default endpoint with the `OMNIROUTE_BASE_URL`
environment variable. Any base URL that resolves to a private or local address
is rejected unless it is `host.docker.internal`, `localhost` or `127.0.0.1`
(SSRF guard).

### Running without Docker

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Requirements on the host:

- **Python 3.10+** (developed and tested on 3.14).
- **ffmpeg** on `PATH` (needed to convert uploads to WAV/MP3).
- Set `DIKTE_WEB_PASSWORD` or read the password the app generates and stores
  in `web_password` on first start (see *Authentication* below).

---

## Configuration

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DIKTE_WEB_PASSWORD` | generated | The single login password. If unset, one is generated and stored in `web_password` (0600 perms, never logged). |
| `XDG_CONFIG_HOME` | `~/.config` | Base for `dikte/config.json`. |
| `XDG_DATA_HOME` | `~/.local/share` | Base for `dikte/` data: history, meetings, recordings, `web_password`, `assistant.json`. |
| `OPENAI_API_KEY` | — | Convenience env; Settings is the source of truth. |
| `GROQ_API_KEY` | — | Same. |
| `OPENROUTER_API_KEY` | — | Same. |
| `OMNIROUTE_BASE_URL` | `http://host.docker.internal:20128/v1` | Default override for the OmniRoute agent endpoint. |
| `DIKTE_MAX_UPLOAD` | `1073741824` (1 GB) | Max upload size in bytes (413 above it). |

### Data layout

Everything persistent lives under the data dir (`$XDG_DATA_HOME/dikte`, mounted
as `/data` in Docker):

```
dikte/
├── config.json          # settings (web Settings edits this)
├── history.jsonl        # dictation history, one JSON row per line
├── web_password         # generated password (only if DIKTE_WEB_PASSWORD unset)
├── assistant.json       # agent conversation session
├── recordings/          # kept only if keep-audio is enabled
└── meetings/
    ├── meetings.jsonl   # meeting index
    ├── <base>.md        # generated minutes
    └── <base>.wav       # meeting audio
```

### Settings exposed in the web UI

- **General** — `ui_language`
- **Transcription** — provider, per-provider model and API key, speech
  language (`auto`/`tr`/`en`), prompt hint, **cleanup** toggle + model +
  reasoning level, VAD options (`skip_silent`, `silence_db`,
  `speech_margin_db`, `min_voiced_seconds`), hallucination filter, history
  limit.
- **Meetings** — cleanup toggle, model, reasoning, self/other participant
  names, participants list.
- **Assistant** — provider (OpenRouter/OmniRoute), model per provider, base
  URL, session length in minutes, timeout.

### Local models

- **Settings → Models** — install the `whisper.cpp` / `llama.cpp` binaries and
  model files (whisper `.bin` models, GGUF quant files) directly from the web
  UI.
- **Transcription** — set `transcribe_provider` to `local` to transcribe with
  whisper.cpp on this machine (no API key).
- **Cleanup** — set `cleanup_provider` to `local-llm` to clean up transcripts
  with llama.cpp locally.
- **Data paths** — binaries at `/data/share/dikte/bin`, models at
  `/data/share/dikte/models` (under the `dikte_data` volume in Docker).

---

## Authentication

- Single shared password; no per-user accounts.
- Login issues a signed, **httponly**, `SameSite=Lax` session cookie that
  expires after **7 days**.
- The cookie is HMAC-signed with a per-process random pepper, so it cannot be
  forged across restarts.
- If `DIKTE_WEB_PASSWORD` is not set, a random password is generated and saved
  to `web_password` (0600 perms); it is never logged.

> **Security note:** this is a single-user app guarded by a single password.
> Do not expose it to the public internet. Run it on your own network or behind
> a reverse proxy with TLS.

---

## HTTP API

The app is a thin JSON API driven by HTMX. All endpoints below are behind the
login gate (`/api/*` → `401` without a session).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/login` | Log in (form field `password`). |
| `GET` | `/logout` | Log out. |
| `POST` | `/api/dictate` | Start a dictation job (multipart `audio`). |
| `POST` | `/api/files/transcribe` | Start a file transcription job (`file`, `timestamps`, `cleanup`). |
| `POST` | `/api/meetings` | Start a meeting job (`file`, `participants`). |
| `GET` | `/api/meetings` | List meetings (newest first). |
| `GET` | `/api/meetings/{base}` | Meeting detail + generated doc. |
| `POST` | `/api/meetings/{base}/retry` | Re-run a meeting pipeline. |
| `DELETE` | `/api/meetings/{base}` | Delete a meeting. |
| `POST` | `/api/agent` | Ask the agent (`{"question": "…"}`). |
| `GET` | `/api/jobs/{id}` | Poll a job's status/result. |
| `GET` | `/api/jobs/{id}/download?format=txt\|srt` | Download a transcript. |
| `GET` | `/api/history` | List history. |
| `POST` | `/api/history/clear` | Clear history. |
| `DELETE` | `/api/history` | Delete selected rows (`{"rows": […]}`). |
| `GET` | `/api/settings` | Read settings (keys masked). |
| `POST` | `/api/settings` | Save settings. |
| `GET` | `/healthz` | Liveness probe (public, checks the config file is readable). |

### Jobs

Transcription and meeting work runs on background threads. `POST` endpoints
return a `{"job_id": …}` immediately; the client polls
`GET /api/jobs/{id}` until `status` is `done` or `failed`. Only one heavy job
runs at a time — submitting a second one returns **`409 Conflict`**. Completed
jobs are pruned automatically (keeps the last 100).

---

## Development

```bash
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

- The test suite is **412 tests / 895 subtests**, all green (some POSIX-only
  chmod tests skip on Windows).
- Tests mock the network (providers) and ffmpeg conversions; the core functions
  generate real WAV files so pipelines run end to end.

```
pytest                     # run everything
pytest tests/test_routes.py -v   # the web E2E suite
```

## Project layout

```
app/
├── main.py                # FastAPI app, auth gate, /healthz
├── auth.py                # single-password login + signed cookie
├── jobs.py                # background job runner (1 at a time, prune)
├── settings.py            # web-facing settings slice + masking
├── rms.py                 # audio level series (for the waveform)
├── routes/
│   ├── pages.py           # HTML pages (Jinja2)
│   └── api.py             # JSON endpoints
├── static/                # CSS, app.js, recorder.js, htmx
├── templates/             # dictation, files, meetings, agent, history, settings
└── vendor/dikte/          # the (Qt-free) upstream engine:
    ├── api.py             # OpenAI/Groq/OpenRouter/local HTTP calls
    ├── worker.py          # dictation pipeline
    ├── filetranscribe.py  # file → txt/srt pipeline
    ├── meeting.py         # meeting → minutes pipeline
    ├── assistant.py       # agent (OpenRouter / OmniRoute)
    ├── cleanup.py         # cleanup model calls
    ├── config.py          # settings storage + defaults + prompts
    ├── vad.py             # voice activity detection
    ├── ggml.py            # local whisper.cpp / llama.cpp support
    ├── signals.py         # progress emission
    └── i18n.py            # en/tr string table
tests/                     # full suite (unit + web E2E)
```

## Credits

- Original project: **[yusufipk/dikte](https://github.com/yusufipk/dikte)** —
  voice-to-text dictation app for Linux. All core engine code is derived from
  it.
- This fork removes the Qt desktop UI and adds a FastAPI + HTMX web interface,
  single-password auth, background jobs, local whisper.cpp/llama.cpp support,
  and Docker packaging.

## Security

- **Single password + rate limiting.** The app is guarded by one shared
  password (`DIKTE_WEB_PASSWORD`). Login is rate-limited per client IP
  (5 failed attempts per 15 minutes → `429`), and the password is compared
  with a constant-time check.
- **Session cookie.** `dikte_session` is `HttpOnly`, `SameSite=Lax` and
  `Secure` by default (`DIKTE_COOKIE_SECURE=1`). Set `DIKTE_COOKIE_SECURE=0`
  only if you run over plain HTTP on a trusted network.
- **TLS required — but no reverse proxy needed.** The service binds to loopback
  only (`127.0.0.1:8000`). Put a Caddy/nginx/Traefik proxy in front with TLS,
  or — simplest — expose it through a [Cloudflare Tunnel
  (`cloudflared`)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  as described above, which terminates TLS at Cloudflare's edge and tunnels to
  the loopback port. Do not expose port 8000 directly to the internet.
- **CSRF defense.** Mutating requests are checked against the same-origin
  `Origin`/`Referer` header; cross-site requests are rejected with `403`.
- **Markdown is sanitized.** Meeting minutes rendered as HTML are passed through
  the nh3 HTML sanitizer, blocking stored XSS from transcript content.
- **Keep the volume private.** The `dikte_data` volume holds API keys (in
  `config.json`) and meeting recordings in plaintext. Back it up regularly and
  keep it on filesystems only you can read.

## License

See the upstream project for the original license terms. This fork keeps the
same license as [yusufipk/dikte](https://github.com/yusufipk/dikte).
