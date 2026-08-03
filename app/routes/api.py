"""Web sayfalarının JSON API'si. Auth gate main.py'deki middleware'dedir."""

import os
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

import api
import assistant
import config as cfg
import filetranscribe as ft
import ggml
import meeting
import vad
import worker

from app import auth, jobs, rms, settings as web_settings

router = APIRouter()

MAX_UPLOAD = int(os.environ.get("DIKTE_MAX_UPLOAD", str(1024 ** 3)))
MAX_AUDIO_SECONDS = 4 * 3600
MAX_QUESTION_CHARS = 4000


def _valid_base(base):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", base))


def _check_duration(duration):
    if duration > MAX_AUDIO_SECONDS:
        raise RuntimeError("Recording is longer than the 4 hour limit")


def _conf(request):
    return request.app.state.conf


def _save_upload(upload: UploadFile) -> str:
    """Upload'u kalıcı bir temp dosyaya yazar (job çalışırken silinmez)."""
    if upload.size is not None and upload.size > MAX_UPLOAD:
        raise HTTPException(413, detail="upload too large")
    suffix = os.path.splitext(upload.filename or "")[1]
    fd, path = tempfile.mkstemp(prefix="dikte-upload-", suffix=suffix)
    os.close(fd)
    try:
        with open(path, "wb") as fh:
            total = 0
            while chunk := upload.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, detail="upload too large")
                fh.write(chunk)
    except Exception:
        os.unlink(path)
        raise
    return path


def _unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def _start(request, kind, work, cleanup=None):
    try:
        job_id = jobs.submit(kind, work)
    except jobs.BusyError:
        if cleanup:
            cleanup()
        raise HTTPException(409, detail="A job is already running.")
    return {"job_id": job_id}


def _pct(done, total):
    if not total:
        return "?"
    return f"{int(done * 100 / total)}%"


def _hydrate_local(conf):
    if conf["transcribe_provider"] == "local":
        ggml.whisper.configure(
            model=conf["local_model"], threads=conf["local_threads"],
            gpu=conf["local_gpu"], binary=conf["local_binary"])
    if conf["cleanup_provider"] == "local-llm":
        ggml.llm.configure(
            model=conf["local_llm_model"], threads=conf["local_llm_threads"],
            gpu=conf["local_llm_gpu"], binary=conf["local_llm_binary"],
            context=conf["local_llm_context"])


@router.get("/api/models")
def list_models(request: Request):
    whisper, llm = [], []
    whisper_error, llm_error = "", ""
    try:
        whisper = [{"name": m.name, "size": m.size, "url": m.url,
                    "path": str(ggml.whisper_model_path(m.name)),
                    "installed": m.name in ggml.installed_whisper_models()}
                   for m in ggml.whisper_models()]
    except Exception as exc:
        whisper_error = str(exc)
    try:
        llm = [{"repo": r,
                "quants": [{"name": q.name, "size": q.size, "url": q.url,
                            "path": str(ggml.llm_model_path(q.name)),
                            "installed": q.name in ggml.installed_llm_models()}
                           for q in ggml.llm_quants(r)]}
               for r in ggml.llm_repos()]
    except Exception as exc:
        llm_error = str(exc)
    programs = [{"name": p.name,
                 "installed": bool(ggml.installed_program(p)),
                 "version": ggml.installed_version(p),
                 "system": ggml.system_program(p)}
                for p in (ggml.WHISPER, ggml.LLAMA)]
    out = {"whisper_models": whisper, "llm": llm, "programs": programs}
    if whisper_error:
        out["whisper_error"] = whisper_error
    if llm_error:
        out["llm_error"] = llm_error
    return out


@router.post("/api/models/install")
def install_model(request: Request, payload: dict = Body(...)):
    kind = str(payload.get("kind") or "")
    name = str(payload.get("name") or "")
    repo = str(payload.get("repo") or "")
    conf = _conf(request)

    if kind == "program" and name not in ("whisper", "llama"):
        raise HTTPException(400, detail="unknown program")
    if kind == "llm" and repo not in ggml.llm_repos():
        raise HTTPException(400, detail="repo not allowed")

    def work(emit):
        if kind == "program":
            program = ggml.WHISPER if name == "whisper" else ggml.LLAMA
            emit("Looking up the release…")
            path = ggml.install_program(
                program,
                on_progress=lambda done, total:
                    emit(f"Downloading… {_pct(done, total)}"))
            return {"path": path}
        if kind == "whisper":
            item = next((m for m in ggml.whisper_models() if m.name == name), None)
            if item is None:
                raise HTTPException(404, detail="no such whisper model")
            target = ggml.whisper_model_path(name)
            ok = ggml.download(item, target,
                               on_progress=lambda done, total:
                                   emit(f"Downloading… {_pct(done, total)}"))
            if ok:
                conf["local_model"] = name
                conf.save()
            return {"path": str(target), "installed": ok}
        if kind == "llm":
            item = next((q for q in ggml.llm_quants(repo) if q.name == name), None)
            if item is None:
                raise HTTPException(404, detail="no such model")
            target = ggml.llm_model_path(name)
            ok = ggml.download(item, target,
                               on_progress=lambda done, total:
                                   emit(f"Downloading… {_pct(done, total)}"))
            if ok:
                conf["local_llm_model"] = name
                conf.save()
            return {"path": str(target), "installed": ok}
        raise HTTPException(400, detail="unknown kind")

    return _start(request, "model", work)


@router.post("/api/models/delete")
def delete_model_route(request: Request, payload: dict = Body(...)):
    path = str(payload.get("path") or "")
    if not path:
        raise HTTPException(400, detail="no path")
    resolved = Path(path).resolve()
    models_dir = Path(ggml.MODELS_DIR).resolve()
    if not resolved.is_relative_to(models_dir):
        raise HTTPException(400, detail="path outside the models directory")
    try:
        ggml.delete_model(path)
    except ggml.LocalError as exc:
        raise HTTPException(400, detail=str(exc))
    return {"deleted": True}


@router.get("/api/jobs/{job_id}")
def job_status(request: Request, job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, detail="no such job")
    return job.as_dict()


@router.post("/api/dictate")
async def dictate(request: Request, audio: UploadFile = File(...)):
    path = _save_upload(audio)
    conf = _conf(request)

    def work(emit):
        _hydrate_local(conf)
        workdir = tempfile.mkdtemp(prefix="dikte-dict-")
        try:
            wav = ft._to_wav(path, workdir)
            duration = ft.wav_seconds(wav)
            _check_duration(duration)
            rms_values = rms.series(wav)
            pipeline = worker.Pipeline(conf)
            pipeline.stage.connect(emit)
            raw, text, warning = pipeline.run(wav, duration, rms_values)
            return {"raw": raw, "text": text, "warning": warning}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            if os.path.exists(path):
                os.unlink(path)

    return _start(request, "dictation", work, cleanup=lambda: _unlink(path))


@router.post("/api/files/transcribe")
async def transcribe_file(request: Request, file: UploadFile = File(...),
                          timestamps: str = Form(""),
                          cleanup: str = Form("")):
    path = _save_upload(file)
    conf = _conf(request)
    want_ts = timestamps == "on"
    do_cleanup = cleanup == "on"

    def work(emit):
        _hydrate_local(conf)
        if not shutil.which("ffmpeg"):
            raise api.ApiError(
                api.t("ffmpeg not found. Install it to transcribe files."))
        workdir = tempfile.mkdtemp(prefix="dikte-file-")
        try:
            wav = ft._to_wav(path, workdir)
            _check_duration(ft.wav_seconds(wav))
            transcriber = ft.FileTranscriber(conf)
            transcriber.progress.connect(emit)
            text, segments = transcriber.transcribe(wav, want_ts, do_cleanup)
            srt = ft.to_srt(text, segments) if want_ts else ""
            return {"text": text, "segments": [list(s) for s in segments],
                    "srt": srt}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            if os.path.exists(path):
                os.unlink(path)

    return _start(request, "file", work, cleanup=lambda: _unlink(path))


@router.get("/api/jobs/{job_id}/download")
def download(request: Request, job_id: str, fmt: str = "txt"):
    job = jobs.get(job_id)
    if job is None or not job.result:
        raise HTTPException(404, detail="no such job")
    if fmt == "srt" and job.result.get("srt"):
        body, name = job.result["srt"], "transcript.srt"
    else:
        body, name = job.result.get("text", ""), "transcript.txt"
    return Response(content=body, media_type="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


def _meeting_wav(path, workdir):
    """Kanalları koruyarak WAV'a çevirir (toplantı stereo gerekir)."""
    out = os.path.join(workdir, "meeting.wav")
    return ft._ffmpeg(["-i", path, "-vn", "-ar", "16000",
                       "-c:a", "pcm_s16le", out], out)


@router.get("/api/meetings")
def list_meetings(request: Request):
    rows = cfg.read_meetings()
    rows.reverse()
    return {"meetings": rows}


@router.post("/api/meetings")
async def create_meeting(request: Request, file: UploadFile = File(...),
                         participants: str = Form("")):
    path = _save_upload(file)
    conf = _conf(request)

    def work(emit):
        _hydrate_local(conf)
        workdir = tempfile.mkdtemp(prefix="dikte-meet-")
        try:
            wav = _meeting_wav(path, workdir)
            duration = ft.wav_seconds(wav)
            _check_duration(duration)
            base = meeting.new_base()
            if not _valid_base(base):
                raise RuntimeError("invalid meeting id")
            entry = meeting.new_entry(base, duration)
            cfg.save_meeting(entry)
            target_wav = cfg.meeting_paths(base)[1]
            target_wav.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(wav, target_wav)
            if participants.strip():
                conf["meeting_participants"] = participants
            pipeline = meeting.MeetingPipeline(conf)
            pipeline.progress.connect(lambda b, msg: emit(msg))
            title = pipeline.run(entry)
            return {"base": base, "title": title}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            if os.path.exists(path):
                os.unlink(path)

    return _start(request, "meeting", work, cleanup=lambda: _unlink(path))


@router.get("/api/meetings/{base}")
def meeting_detail(request: Request, base: str):
    if not _valid_base(base):
        raise HTTPException(400, detail="invalid meeting id")
    row = next((r for r in cfg.read_meetings() if r["base"] == base), None)
    if row is None:
        raise HTTPException(404)
    doc_path = cfg.meeting_paths(base)[0]
    doc = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    return {"meeting": row, "doc": doc}


@router.post("/api/meetings/{base}/retry")
def retry_meeting(request: Request, base: str):
    if not _valid_base(base):
        raise HTTPException(400, detail="invalid meeting id")
    row = next((r for r in cfg.read_meetings() if r["base"] == base), None)
    if row is None:
        raise HTTPException(404)
    conf = _conf(request)

    def work(emit):
        _hydrate_local(conf)
        pipeline = meeting.MeetingPipeline(conf)
        pipeline.progress.connect(lambda b, msg: emit(msg))
        title = pipeline.run(row)
        return {"base": base, "title": title}

    return _start(request, "meeting", work)


@router.delete("/api/meetings/{base}")
def delete_meeting(request: Request, base: str):
    if not _valid_base(base):
        raise HTTPException(400, detail="invalid meeting id")
    if not any(row["base"] == base for row in cfg.read_meetings()):
        raise HTTPException(404)
    cfg.delete_meetings([base])
    return {"deleted": base}


@router.post("/api/agent")
def ask_agent(request: Request, payload: dict = Body(...)):
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, detail="empty question")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, detail="question too long")
    try:
        answer, _warning = assistant.ask(
            question, _conf(request),
            provider=str(payload.get("provider") or ""),
            model=str(payload.get("model") or ""),
        )
    except assistant.AssistantError as exc:
        raise HTTPException(400, detail=str(exc))
    return {"answer": answer}


@router.get("/api/history")
def history(request: Request):
    rows = cfg.read_history()
    rows.reverse()
    return {"entries": rows}


@router.delete("/api/history")
def delete_history(request: Request, payload: dict = Body(...)):
    rows = payload.get("rows") or []
    cfg.delete_history(rows)
    return {"deleted": len(rows)}


@router.post("/api/history/clear")
def clear_history():
    cfg.clear_history()
    return {"cleared": True}


@router.get("/api/settings")
def get_settings(request: Request):
    return {"settings": web_settings.present(_conf(request))}


@router.post("/api/settings")
def post_settings(request: Request, payload: dict = Body(...)):
    web_settings.apply(_conf(request), payload.get("settings") or {})
    return {"saved": True}
