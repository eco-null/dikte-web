function ensureSpinner(el) {
  if (!el) return null;
  let s = el.querySelector(".spinner");
  if (!s) {
    s = document.createElement("span");
    s.className = "spinner";
    s.setAttribute("aria-hidden", "true");
    el.prepend(s);
  }
  return s;
}
function setSpinner(el, on) {
  if (!el) return;
  const s = ensureSpinner(el);
  if (s) s.style.display = on ? "inline-block" : "none";
  el.classList.toggle("has-spinner", on);
}

function setStage(el, text) {
  if (!el) return;
  // keep an existing spinner span as the first child; replace the rest with the text
  const spinner = el.querySelector(":scope > .spinner");
  el.textContent = text || "";
  if (spinner) el.prepend(spinner);
}

function autoGrow(el) {
  if (!el) return;
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 600) + "px";
}

function pollJob(jobId, els, everyMs) {
  everyMs = everyMs || 2000;
  setStage(els.stage, "Waiting…");
  setSpinner(els.stage, true);
  const tick = async () => {
    let resp, job;
    try {
      resp = await fetch("/api/jobs/" + jobId);
      job = await resp.json();
    } catch (err) {
      setSpinner(els.stage, false);
      setStage(els.stage, "Could not reach the server: " + err);
      return;
    }
    setStage(els.stage, job.status === "running" ? (job.stage || "Working…") : job.status);
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
      setStage(els.stage, "");
      setSpinner(els.stage, false);
      return;
    }
    if (job.status === "failed") {
      setStage(els.stage, job.error || "Failed");
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
