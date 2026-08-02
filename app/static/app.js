function pollJob(jobId, els, everyMs) {
  everyMs = everyMs || 2000;
  els.stage.textContent = "Waiting…";
  const tick = async () => {
    const resp = await fetch("/api/jobs/" + jobId);
    const job = await resp.json();
    els.stage.textContent = job.status === "running" ? (job.stage || "Working…") : job.status;
    if (job.status === "done") {
      const text = (job.result && job.result.text) || "";
      els.textEl.value = text;
      if (job.result && job.result.warning) {
        const w = document.createElement("p");
        w.className = "warn";
        w.textContent = job.result.warning;
        els.resultBox.prepend(w);
      }
      els.resultBox.hidden = false;
      els.stage.textContent = "";
      return;
    }
    if (job.status === "failed") {
      els.stage.textContent = job.error || "Failed";
      return;
    }
    setTimeout(tick, everyMs);
  };
  tick();
}

document.addEventListener("click", (e) => {
  const copy = e.target.closest("[data-copy]");
  if (copy) {
    const target = copy.dataset.target;
    const src = target ? document.querySelector(target) : copy;
    const text = src ? (src.value || src.textContent) : "";
    navigator.clipboard.writeText(text);
    return;
  }
  const dl = e.target.closest("[data-download]");
  if (dl) {
    window.location.href = "/api/jobs/" + dl.dataset.jobId + "/download?format=" + (dl.dataset.fmt || "txt");
  }
});
