function setSpinner(el, on) {
  if (!el) return;
  if (on) { el.classList.add("spinner"); } else { el.classList.remove("spinner"); }
}

function autoGrow(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 600) + "px";
}

function pollJob(jobId, els, everyMs) {
  everyMs = everyMs || 2000;
  els.stage.textContent = "Waiting…";
  setSpinner(els.stage, true);
  const tick = async () => {
    let resp, job;
    try {
      resp = await fetch("/api/jobs/" + jobId);
      job = await resp.json();
    } catch (err) {
      setSpinner(els.stage, false);
      els.stage.textContent = "Could not reach the server: " + err;
      return;
    }
    els.stage.textContent = job.status === "running" ? (job.stage || "Working…") : job.status;
    if (job.status === "done") {
      const text = (job.result && job.result.text) || "";
      els.textEl.value = text;
      autoGrow(els.textEl);
      if (job.result && job.result.warning) {
        const w = document.createElement("p");
        w.className = "warn";
        w.textContent = job.result.warning;
        els.resultBox.prepend(w);
      }
      els.resultBox.hidden = false;
      els.stage.textContent = "";
      setSpinner(els.stage, false);
      return;
    }
    if (job.status === "failed") {
      els.stage.textContent = job.error || "Failed";
      setSpinner(els.stage, false);
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
    window.location.href = "/api/jobs/" + dl.dataset.jobId + "/download?fmt=" + (dl.dataset.fmt || "txt");
  }
});
