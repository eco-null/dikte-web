(function () {
  let recorder = null, stream = null, chunks = [], analyser = null, raf = null;
  const canvas = document.getElementById("meter");
  const ctx2 = canvas ? canvas.getContext("2d") : null;
  const stage = document.getElementById("stage");
  const btnRecord = document.getElementById("record");
  const btnStop = document.getElementById("stop");
  const btnCancel = document.getElementById("cancel");
  const resultBox = document.getElementById("result");
  const textEl = document.getElementById("text");
  if (!btnRecord) return;

  function setBusy(busy) {
    btnRecord.disabled = busy;
    btnStop.disabled = !busy;
    btnCancel.disabled = !busy;
    btnRecord.classList.toggle("recording", busy);
  }
  function draw() {
    if (!ctx2 || !analyser) return;
    const data = new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (const v of data) { const d = v - 128; sum += d * d; }
    const level = Math.min(1, Math.sqrt(sum / data.length) / 128);
    ctx2.clearRect(0, 0, canvas.width, canvas.height);
    ctx2.fillStyle = "var(--color-accent)";
    ctx2.fillRect(0, canvas.height * (1 - level), canvas.width * level, canvas.height);
    raf = requestAnimationFrame(draw);
  }

  btnRecord.addEventListener("click", async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      stopStream();
      setBusy(false);
      stage.textContent = "Microphone error: " + err;
      return;
    }
    chunks = [];
    const ac = new AudioContext();
    const src = ac.createMediaStreamSource(stream);
    analyser = ac.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    recorder = new MediaRecorder(stream);
    recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    recorder.onstop = upload;
    recorder.start();
    setBusy(true);
    stage.textContent = "Recording…";
    raf = requestAnimationFrame(draw);
  });

  function stop() { if (recorder) recorder.stop(); }
  function cancel() {
    if (recorder) { recorder.onstop = null; recorder.stop(); }
    stopStream();
    setBusy(false);
    stage.textContent = "";
  }

  function stopStream() {
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
    if (raf) cancelAnimationFrame(raf);
    if (analyser) { analyser = null; }
  }

  async function upload() {
    stopStream();
    setBusy(false);
    const blob = new Blob(chunks, { type: recorder ? recorder.mimeType || "audio/webm" : "audio/webm" });
    if (blob.size === 0) { stage.textContent = "Nothing recorded."; return; }
    const fd = new FormData();
    fd.append("audio", blob, "recording.webm");
    stage.textContent = "Uploading…";
    let jobId;
    try {
      const resp = await fetch("/api/dictate", { method: "POST", body: fd });
      if (resp.status === 409) { stage.textContent = "Busy, one job at a time"; return; }
      if (!resp.ok) { stage.textContent = (await resp.json()).detail || resp.status; return; }
      jobId = (await resp.json()).job_id;
    } catch (err) { stage.textContent = "Upload failed: " + err; return; }
    const dlBtn = document.getElementById("download");
    if (dlBtn) dlBtn.dataset.jobId = jobId;
    pollJob(jobId, { stage, resultBox, textEl });
  }

  btnStop.addEventListener("click", stop);
  btnCancel.addEventListener("click", cancel);
  setBusy(false);
})();
