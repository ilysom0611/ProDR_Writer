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

async function api(path, opts) {
  const res = await fetch(path, opts);
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
    showStatus(`Saved. ${f.base_url.value ? "" : ""}`, "");
    toast("Configuration saved", "ok");
    loadConfig();
  } catch (e) { toast(`Save failed: ${e.message}`, "err"); }
});

$("#btn-test").addEventListener("click", async () => {
  const btn = $("#btn-test");
  btn.disabled = true; btn.textContent = "Testing…";
  try {
    const r = await api("/api/config/test", { method: "POST" });
    showStatus(r.message, r.ok ? "ok" : "err");
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

function renderStages() {
  const ol = $("#stage-list");
  ol.innerHTML = "";
  STAGES.forEach((key) => {
    const li = document.createElement("li");
    li.dataset.stage = key;
    li.innerHTML = `<span class="dot"></span><span>${STAGE_LABELS[key]}</span>`;
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

async function startJob(endpoint, payload, title) {
  renderStages();
  $("#progress-card").classList.remove("hidden");
  $("#result-box").classList.add("hidden");
  $("#error-box").classList.add("hidden");
  $("#review-note").classList.add("hidden");
  $("#job-project").textContent = `— ${title}`;
  $("#btn-generate").disabled = true;
  $("#btn-demo").disabled = true;

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

  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    if (event.type === "stage") {
      setStage(event.stage, event.status, event.label);
    } else if (event.type === "review") {
      const note = $("#review-note");
      note.textContent = `Review round ${event.round}: score ${event.score}/100 — ${event.passed ? "passed ✓" : "optimizing…"}`;
      note.classList.remove("hidden");
    } else if (event.type === "done" || event.type === "success") {
      es.close();
      showResult(event.summary);
      resetButtons();
    } else if (event.type === "error") {
      es.close();
      showError(event.error || "Generation failed");
      resetButtons();
    }
  };
  es.onerror = () => { /* server closes the stream on completion */ };
}

function showResult(summary) {
  const score = summary.score != null ? `, review score ${summary.score}/100` : "";
  $("#result-text").innerHTML =
    `<strong>Done!</strong> Document generated${score}. ` +
    `Fatal findings: ${summary.fatal_findings ?? 0}, warnings: ${summary.warnings ?? 0}.`;
  $("#download-link").href =
    `/api/history/${encodeURIComponent(summary.docx.split(/[\\\\/]/).slice(-2)[0])}/download`;
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
async function loadHistory() {
  try {
    const { runs } = await api("/api/history");
    const tbody = $("#history-table tbody");
    tbody.innerHTML = "";
    $("#history-empty").hidden = runs.length > 0;
    runs.forEach((run) => {
      const tr = document.createElement("tr");
      const badge = run.status === "demo" ? '<span class="badge ok">demo</span>'
        : run.fatal_findings ? `<span class="badge err">${run.fatal_findings} fatal</span>`
        : run.score != null ? `<span class="badge ok">score ${run.score}</span>`
        : '<span class="badge warn">legacy</span>';
      tr.innerHTML = `
        <td>${run.name}</td>
        <td>${run.project_name || "-"}</td>
        <td>${(run.language || "-").toUpperCase()}</td>
        <td>${badge}</td>
        <td>${run.downloadable ? `<a href="/api/history/${encodeURIComponent(run.name)}/download">⬇ Download</a>` : "-"}</td>`;
      tbody.appendChild(tr);
    });
  } catch (e) { toast(`Failed to load history: ${e.message}`, "err"); }
}

loadMeta();
loadHistory();
