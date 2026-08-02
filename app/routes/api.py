"""Web sayfalarının JSON API'si. Auth gate main.py'deki middleware'dedir."""

import os
import shutil
import tempfile

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

import api
import assistant
import config as cfg
import filetranscribe as ft
import meeting
import vad
import worker

from app import auth, jobs, rms, settings as web_settings

router = APIRouter()

MAX_UPLOAD = int(os.environ.get("DIKTE_MAX_UPLOAD", str(1024 ** 3)))


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
            shutil.copyfileobj(upload.file, fh)
    except Exception:
        os.unlink(path)
        raise
    return path


def _start(request, kind, work):
    try:
        job_id = jobs.submit(kind, work)
    except jobs.BusyError:
        raise HTTPException(409, detail="A job is already running.")
    return {"job_id": job_id}


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
        workdir = tempfile.mkdtemp(prefix="dikte-dict-")
        try:
            wav = ft._to_wav(path, workdir)
            duration = ft.wav_seconds(wav)
            rms_values = rms.series(wav)
            pipeline = worker.Pipeline(conf)
            pipeline.stage.connect(emit)
            raw, text, warning = pipeline.run(wav, duration, rms_values)
            return {"raw": raw, "text": text, "warning": warning}
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
            if os.path.exists(path):
                os.unlink(path)

    return _start(request, "dictation", work)


@router.post("/api/files/transcribe")
async def transcribe_file(request: Request, file: UploadFile = File(...),
                          timestamps: str = Form(""),
                          cleanup: str = Form("")):
    path = _save_upload(file)
    conf = _conf(request)
    want_ts = timestamps == "on"
    do_cleanup = cleanup == "on"

    def work(emit):
        try:
            transcriber = ft.FileTranscriber(conf)
            transcriber.progress.connect(emit)
            text, segments = transcriber.transcribe(path, want_ts, do_cleanup)
            srt = ft.to_srt(text, segments) if want_ts else ""
            return {"text": text, "segments": [list(s) for s in segments],
                    "srt": srt}
        finally:
            if os.path.exists(path):
                os.unlink(path)

    return _start(request, "file", work)


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
        workdir = tempfile.mkdtemp(prefix="dikte-meet-")
        try:
            wav = _meeting_wav(path, workdir)
            duration = ft.wav_seconds(wav)
            base = meeting.new_base()
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

    return _start(request, "meeting", work)


@router.get("/api/meetings/{base}")
def meeting_detail(request: Request, base: str):
    row = next((r for r in cfg.read_meetings() if r["base"] == base), None)
    if row is None:
        raise HTTPException(404)
    doc_path = cfg.meeting_paths(base)[0]
    doc = doc_path.read_text(encoding="utf-8") if doc_path.exists() else ""
    return {"meeting": row, "doc": doc}


@router.post("/api/meetings/{base}/retry")
def retry_meeting(request: Request, base: str):
    row = next((r for r in cfg.read_meetings() if r["base"] == base), None)
    if row is None:
        raise HTTPException(404)
    conf = _conf(request)

    def work(emit):
        pipeline = meeting.MeetingPipeline(conf)
        pipeline.progress.connect(lambda b, msg: emit(msg))
        title = pipeline.run(row)
        return {"base": base, "title": title}

    return _start(request, "meeting", work)


@router.delete("/api/meetings/{base}")
def delete_meeting(request: Request, base: str):
    cfg.delete_meetings([base])
    return {"deleted": base}


@router.post("/api/agent")
def ask_agent(request: Request, payload: dict = Body(...)):
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, detail="empty question")
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
