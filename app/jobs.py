"""Tek heavy job: kuyruk yok, çakışmada BusyError.

İş, arka planda bir thread'de çalışır; `emit(text)` aşamayı günceller.
Sonuç ve hata job kaydında saklanır, `MAX_JOBS` üzerindeki bitenler temizlenir.
"""

import threading
import time
import uuid


class BusyError(Exception):
    pass


class Job:
    def __init__(self, kind):
        self.id = uuid.uuid4().hex
        self.kind = kind
        self.status = "queued"          # queued | running | done | failed
        self.stage = ""
        self.result = None
        self.error = ""
        self.created = time.time()
        self.started = 0.0
        self.finished = 0.0

    def as_dict(self):
        return {
            "id": self.id, "kind": self.kind, "status": self.status,
            "stage": self.stage, "error": self.error, "result": self.result,
            "created": self.created, "started": self.started,
            "finished": self.finished,
        }


class JobManager:
    def __init__(self, max_jobs=100):
        self._lock = threading.Lock()
        self._jobs = {}
        self._busy = None
        self.max_jobs = max_jobs

    def submit(self, kind, work):
        """work(emit) bir thread'de çalışır; job_id döner.

        Zaten bir iş çalışıyorsa BusyError fırlatır.
        """
        with self._lock:
            if self._busy is not None:
                raise BusyError()
            job = Job(kind)
            self._jobs[job.id] = job
            self._busy = job.id
            self._prune()

        def run():
            job.status = "running"
            job.started = time.time()
            try:
                job.result = work(lambda text: self._stage(job, text))
                job.status = "done"
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)
            finally:
                job.finished = time.time()
                with self._lock:
                    self._busy = None

        threading.Thread(target=run, daemon=True).start()
        return job.id

    def _stage(self, job, text):
        with self._lock:
            job.stage = text

    def get(self, job_id):
        with self._lock:
            return self._jobs.get(job_id)

    def _prune(self):
        finished = [j for j in self._jobs.values() if j.status in ("done", "failed")]
        finished.sort(key=lambda j: j.finished)
        overflow = len(finished) - self.max_jobs
        for job in finished[:overflow]:
            self._jobs.pop(job.id, None)
