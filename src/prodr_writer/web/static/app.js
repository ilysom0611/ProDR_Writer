/* ProDR_Writer web UI */
"use strict";

const $ = (sel) => document.querySelector(sel);
const STAGE_LABELS = {
  bia: "Business impact analysis",
  current_state: "Current state assessment",
  strategy: "DR strategy design",
  architecture: "Architecture design",
  optimizer: "Review optimization",
  document: "Document build",
};

// ---------- auth token (only needed for non-loopback deployments) ----------
function getToken() { return sessionStorage.getItem("prodr_token") || ""; }
function setToken(t) { sessionStorage.setItem("prodr_token", String(t || "").trim()); }
// start.sh/start.bat print the LAN URL with ?token=... appended; pick it up
// once so the user isn't prompted on first use.
(() => {
  const q = new URLSearchParams(window.location.search).get("token");
  if (q && !getToken()) setToken(q);
})();

// ---------- tabs ----------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".panel").forEach((p) =>
      p.classList.toggle("active", p.id === `tab-${btn.dataset.tab}`));
    if (btn.dataset.tab === "history") loadHistory();
    if (btn.dataset.tab === "config") loadConfig();
  });
});

function toast(msg, kind = "") {
  const el = $("#toast");
  el.textContent = msg;
  el.className = `toast ${kind}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

async function api(path, opts = {}) {
  const headers = Object.assign({}, opts.headers);
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res = await fetch(path, Object.assign({}, opts, { headers }));
  if (res.status === 401) {
    // Non-loopback servers require PRODR_WEB_TOKEN; ask once and retry.
    const t = window.prompt("This server requires an API token (PRODR_WEB_TOKEN):");
    if (t != null && t.trim()) {
      setToken(t);
      const retryHeaders = Object.assign({}, opts.headers);
      retryHeaders.Authorization = `Bearer ${getToken()}`;
      res = await fetch(path, Object.assign({}, opts, { headers: retryHeaders }));
    }
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `${res.status} ${res.statusText}`);
  return body;
}

// ---------- metadata (profiles/industries) ----------
async function loadMeta() {
  try {
    const meta = await api("/api/meta");
    for (const sel of [$("#industry-select")]) {
      meta.industries.forEach((i) => sel.add(new Option(i, i)));
    }
    for (const sel of [$("#profile-select"), $("#cfg-profile-select")]) {
      meta.profiles.forEach((p) => sel.add(new Option(p, p)));
    }
  } catch (e) { toast(`Failed to load metadata: ${e.message}`, "err"); }
}

// ---------- config ----------
async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    const form = $("#cfg-form");
    form.base_url.value = cfg.base_url || "";
    form.model.value = cfg.model || "";
    form.temperature.value = cfg.temperature;
    form.language.value = cfg.language;
    form.profile.value = cfg.profile;
    $("#key-hint").textContent = cfg.has_api_key ? `(saved: ${cfg.api_key_masked})` : "(not set)";
  } catch (e) { toast(`Failed to load config: ${e.message}`, "err"); }
}

$("#cfg-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const f = ev.target;
  try {
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_url: f.base_url.value,
        api_key: f.api_key.value || null,
        model: f.model.value,
        temperature: parseFloat(f.temperature.value) || 0.3,
        language: f.language.value,
        profile: f.profile.value,
      }),
    });
    f.api_key.value = "";
    showStatus("Saved.", "");
    toast("Configuration saved", "ok");
    loadConfig();
  } catch (e) { toast(`Save failed: ${e.message}`, "err"); }
});

$("#btn-test").addEventListener("click", async () => {
  const btn = $("#btn-test");
  btn.disabled = true; btn.textContent = "Testing…";
  try {
    const r = await api("/api/config/test", { method: "POST" });
    showStatus(r.ok ? r.message : (r.detail ? `${r.message}: ${r.detail}` : r.message),
               r.ok ? "ok" : "err");
  } catch (e) { showStatus(e.message, "err"); }
  finally { btn.disabled = false; btn.textContent = "🔌 Test connection"; }
});

function showStatus(text, kind) {
  const el = $("#cfg-status");
  el.textContent = text;
  el.className = `note ${kind === "err" ? "error" : ""}`;
  el.classList.remove("hidden");
}

// ---------- generation ----------
const STAGES = ["bia", "current_state", "strategy", "architecture", "optimizer", "document"];
// Survives page refreshes: as long as the job is pending/running we remember
// it here and reattach the progress stream on load.
const ACTIVE_JOB_KEY = "prodr_active_job";

function renderStages() {
  const ol = $("#stage-list");
  ol.innerHTML = "";
  STAGES.forEach((key) => {
    const li = document.createElement("li");
    li.dataset.stage = key;
    // STAGE_LABELS are static constants, not server data — safe to build here.
    const dot = document.createElement("span");
    dot.className = "dot";
    const label = document.createElement("span");
    label.textContent = STAGE_LABELS[key];
    li.append(dot, label);
    ol.appendChild(li);
  });
}

function setStage(stage, status, label) {
  const li = $(`#stage-list li[data-stage="${stage}"]`);
  if (!li) return;
  li.className = status;
  li.querySelector(".dot").textContent = status === "done" ? "✓" : "";
  if (label && status === "running") li.lastElementChild.textContent = label;
}

$("#gen-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const payload = Object.fromEntries(new FormData(ev.target).entries());
  startJob("/api/generate", payload, payload.project_name);
});

$("#btn-demo").addEventListener("click", () => {
  const lang = $("#gen-form").language.value;
  const profile = $("#gen-form").profile.value;
  startJob("/api/demo", { language: lang, profile }, "Demo proposal");
});

// EventSource cannot send headers, so the token rides in the query string
// (the server accepts both). Close after repeated failures instead of
// retrying forever against a restarted/dead server.
function openEventStream(jobId, onEvent, onLost) {
  const token = getToken();
  const url = `/api/jobs/${jobId}/events${token ? `?token=${encodeURIComponent(token)}` : ""}`;
  const es = new EventSource(url);
  let failures = 0;
  es.onmessage = (msg) => { failures = 0; onEvent(JSON.parse(msg.data), es); };
  es.onerror = () => {
    failures += 1;
    if (failures >= 3) {
      es.close();
      onLost("Lost connection to the server. If it was restarted, try again.");
    }
  };
  return es;
}

function showProgressCard(title) {
  renderStages();
  $("#progress-card").classList.remove("hidden");
  $("#result-box").classList.add("hidden");
  $("#error-box").classList.add("hidden");
  $("#review-note").classList.add("hidden");
  $("#job-project").textContent = title ? `— ${title}` : "";
  $("#btn-generate").disabled = true;
  $("#btn-demo").disabled = true;
}

// Shared SSE handler: used both right after POSTing a new job and when
// reattaching to a job after a page refresh. The server replays all stored
// events from position 0, so a reattached client rebuilds the full picture.
function attachJobStream(jobId) {
  openEventStream(jobId, (event, es) => {
    if (event.type === "stage") {
      setStage(event.stage, event.status, event.label);
    } else if (event.type === "retry") {
      const note = $("#review-note");
      note.textContent = `⚠ ${event.stage}: ${event.reason} (LLM retries automatically, up to 3 attempts)` ;
      note.classList.remove("hidden");
    } else if (event.type === "review") {
      const note = $("#review-note");
      note.textContent = `Review round ${event.round}: score ${event.score}/100 — ${event.passed ? "passed ✓" : "optimizing…"}`;
      note.classList.remove("hidden");
    } else if (event.type === "done" || event.type === "success") {
      es.close();
      localStorage.removeItem(ACTIVE_JOB_KEY);
      showResult(event.summary);
      resetButtons();
    } else if (event.type === "cancelled") {
      es.close();
      localStorage.removeItem(ACTIVE_JOB_KEY);
      showError("Generation cancelled.");
      resetButtons();
    } else if (event.type === "error") {
      es.close();
      localStorage.removeItem(ACTIVE_JOB_KEY);
      showError(event.error || "Generation failed");
      resetButtons();
    }
  }, (message) => {
    localStorage.removeItem(ACTIVE_JOB_KEY);
    showError(message);
    resetButtons();
  });
}

async function startJob(endpoint, payload, title) {
  showProgressCard(title);

  let jobId;
  try {
    const r = await api(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    jobId = r.job_id;
  } catch (e) {
    showError(e.message);
    resetButtons();
    return;
  }
  localStorage.setItem(ACTIVE_JOB_KEY, jobId);
  attachJobStream(jobId);
}

// After a refresh the in-progress job is picked up again: pending/running
// jobs resume streaming; finished ones surface their result or error.
async function resumeActiveJob() {
  const jobId = localStorage.getItem(ACTIVE_JOB_KEY);
  if (!jobId) return;
  let job;
  try {
    job = await api(`/api/jobs/${jobId}`);
  } catch (e) {
    localStorage.removeItem(ACTIVE_JOB_KEY); // unknown/expired — forget it
    return;
  }
  if (["done", "error", "cancelled"].includes(job.status)) {
    localStorage.removeItem(ACTIVE_JOB_KEY);
    showProgressCard(job.project_name);
    if (job.status === "done") {
      STAGES.forEach((s) => setStage(s, "done"));
      showResult(job.summary);
    } else if (job.status === "error") {
      showError(job.error || "Generation failed");
      resetButtons();
    } else {
      showError("Generation cancelled.");
      resetButtons();
    }
    return;
  }
  showProgressCard(job.project_name);
  attachJobStream(jobId);
}

function showResult(summary) {
  summary = summary || {};
  const link = $("#download-link");
  const docx = typeof summary.docx === "string" ? summary.docx : "";
  // Server sends only "<run-dir>/<file>.docx" relative to the output directory.
  const parts = docx.split(/[\\/]/);
  const runDir = parts.length >= 2 ? parts[parts.length - 2] : "";
  const score = summary.score != null ? `, review score ${summary.score}/100` : "";

  if (runDir) {
    link.href = `/api/history/${encodeURIComponent(runDir)}/download`;
    link.classList.remove("hidden");
    $("#result-text").textContent =
      `Done! Document generated${score}. ` +
      `Fatal findings: ${summary.fatal_findings ?? 0}, warnings: ${summary.warnings ?? 0}.`;
  } else {
    // No document produced (or none reported) — still a completed run.
    link.classList.add("hidden");
    link.removeAttribute("href");
    $("#result-text").textContent =
      `Done! Run completed${score} but no document was produced.` +
      ` Fatal findings: ${summary.fatal_findings ?? 0}, warnings: ${summary.warnings ?? 0}.`;
  }
  $("#result-box").classList.remove("hidden");
}

function showError(text) {
  $("#error-box").textContent = text;
  $("#error-box").classList.remove("hidden");
}

function resetButtons() {
  $("#btn-generate").disabled = false;
  $("#btn-demo").disabled = false;
}

// ---------- history ----------
function badgeEl(text, kind) {
  const span = document.createElement("span");
  span.className = `badge ${kind}`;
  span.textContent = text;
  return span;
}

async function loadHistory() {
  try {
    const { runs } = await api("/api/history");
    const tbody = $("#history-table tbody");
    tbody.innerHTML = "";
    $("#history-empty").hidden = runs.length > 0;
    runs.forEach((run) => {
      const tr = document.createElement("tr");

      // Columns must match index.html: Run|Project|Language|Score|Fatal|Download.
      // All server-derived values are inserted via textContent — never innerHTML.
      const cells = [
        run.name || "-",
        run.project_name || "-",
        String(run.language || "-").toUpperCase(),
      ];
      cells.forEach((text) => {
        const td = document.createElement("td");
        td.textContent = text;
        tr.appendChild(td);
      });

      const scoreTd = document.createElement("td");
      if (run.status === "error") {
        tr.title = run.error || "Run failed";
        scoreTd.appendChild(badgeEl("failed", "err"));
      } else if (run.status === "demo") scoreTd.appendChild(badgeEl("demo", "ok"));
      else if (run.score != null) scoreTd.appendChild(badgeEl(`score ${run.score}`, "ok"));
      else scoreTd.appendChild(badgeEl("legacy", "warn"));
      tr.appendChild(scoreTd);

      const fatalTd = document.createElement("td");
      if (run.fatal_findings) fatalTd.appendChild(badgeEl(`${run.fatal_findings} fatal`, "err"));
      else fatalTd.textContent = "-";
      tr.appendChild(fatalTd);

      const dlTd = document.createElement("td");
      if (run.downloadable) {
        const a = document.createElement("a");
        a.href = `/api/history/${encodeURIComponent(run.name)}/download`;
        a.textContent = "⬇ Download";
        dlTd.appendChild(a);
      } else {
        dlTd.textContent = "-";
      }
      tr.appendChild(dlTd);

      tbody.appendChild(tr);
    });
  } catch (e) { toast(`Failed to load history: ${e.message}`, "err"); }
}

loadMeta();
loadHistory();
resumeActiveJob();
