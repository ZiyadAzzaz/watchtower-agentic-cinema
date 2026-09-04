const state = { data: null, incidents: new Map(), busy: false };
const el = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const regions = ["North America", "Europe", "MENA", "South Asia", "Latin America"];

function token() { return sessionStorage.getItem("watchtower-admin-token") || ""; }
function headers() { return { "Content-Type": "application/json", "X-Watchtower-Token": token() }; }
function escapeHtml(value) { const node = document.createElement("span"); node.textContent = String(value ?? ""); return node.innerHTML; }
function toast(message, error = false) { const box = el("toast"); box.textContent = message; box.className = `toast show${error ? " error" : ""}`; clearTimeout(toast.timer); toast.timer = setTimeout(() => box.className = "toast", 3500); }

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `Request failed (${response.status})`);
  return body;
}

async function refresh() {
  if (state.busy) return;
  state.busy = true;
  try {
    state.data = await api("/api/dashboard");
    render();
    el("systemState").textContent = "Operational";
  } catch (error) {
    el("systemState").textContent = "Telemetry unavailable";
    toast(error.message, true);
  } finally { state.busy = false; }
}

function render() {
  const summary = state.data.summary || {};
  const status = state.data.status || {};
  el("viewsMetric").textContent = fmt.format(Number(summary.views || 0));
  el("startsMetric").textContent = fmt.format(Number(summary.total_starts || 0));
  el("bufferMetric").textContent = `${(Number(summary.buffer_rate || 0) * 100).toFixed(2)}%`;
  el("adsMetric").textContent = fmt.format(Number(summary.ad_impressions || 0));
  el("eventsMetric").textContent = `${fmt.format(status.events_ingested || 0)} events retained`;
  el("bufferHealth").textContent = Number(summary.buffer_rate || 0) < .06 ? "Baseline healthy" : "Elevated signal";
  el("lastEvent").textContent = summary.last_event_at ? `Updated ${relativeTime(summary.last_event_at)}` : "No event yet";
  el("pendingCount").textContent = status.pending_incidents || 0;
  renderChart(state.data.timeseries || []);
  renderIncidents(state.data.incidents || []);
  renderCatalog(state.data.titles || []);
}

function renderChart(rows) {
  const svg = el("signalChart");
  const values = rows.map(row => Number(row.views || 0));
  if (values.length < 2) { svg.innerHTML = `<text x="360" y="120" text-anchor="middle" fill="#59636e" font-size="11">Building live signal…</text>`; return; }
  const width = 720, height = 220, pad = 10;
  const min = Math.min(...values) * .92, max = Math.max(...values) * 1.05;
  const points = values.map((value, index) => {
    const x = pad + index * (width - pad * 2) / (values.length - 1);
    const y = height - pad - ((value - min) / Math.max(1, max - min)) * (height - pad * 2);
    return [x, y];
  });
  const line = points.map(([x,y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${line} L${points.at(-1)[0]},${height} L${points[0][0]},${height} Z`;
  const grid = [45, 95, 145, 195].map(y => `<line class="chart-grid" x1="0" y1="${y}" x2="720" y2="${y}"/>`).join("");
  const [lastX,lastY] = points.at(-1);
  svg.innerHTML = `<defs><linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#54e4ce" stop-opacity=".18"/><stop offset="1" stop-color="#54e4ce" stop-opacity="0"/></linearGradient></defs>${grid}<path class="chart-area" d="${area}"/><path class="chart-line" d="${line}"/><circle class="chart-dot" cx="${lastX}" cy="${lastY}" r="4"/>`;
}

function renderIncidents(incidents) {
  const list = el("incidentList");
  state.incidents = new Map(incidents.map(item => [item.id, item]));
  if (!incidents.length) { list.innerHTML = `<div class="empty-state"><div class="empty-radar"><i></i></div><h3>All signals within range</h3><p>WatchTower is comparing live delivery telemetry against rolling baselines.</p></div>`; return; }
  list.innerHTML = incidents.map(incident => {
    const anomaly = incident.anomaly, impact = incident.impact;
    return `<article class="incident-card"><i class="severity-bar ${impact.severity}"></i><div class="incident-main"><span>${escapeHtml(anomaly.kind.replaceAll("_", " ").toUpperCase())} · ${escapeHtml(anomaly.region.toUpperCase())}</span><h3>${escapeHtml(anomaly.title_name)}</h3><p>${escapeHtml(incident.root_cause.primary_value)} · detected ${relativeTime(incident.created_at)}</p></div><div class="incident-metric"><span>ESTIMATED IMPACT</span><b>${money.format(impact.estimated_revenue_loss_usd)}</b></div><div class="incident-metric"><span>VIEWER-HOURS</span><b>${fmt.format(impact.lost_viewer_hours)}</b></div><span class="status-pill ${incident.status}">${escapeHtml(incident.status.replaceAll("_", " "))}</span><button class="view-button" data-incident="${incident.id}">Review →</button></article>`;
  }).join("");
  document.querySelectorAll("[data-incident]").forEach(button => button.addEventListener("click", () => openIncident(button.dataset.incident)));
}

function renderCatalog(titles) {
  if (el("catalogGrid").dataset.rendered) return;
  el("catalogGrid").innerHTML = titles.map(title => `<article class="title-card" style="--from:${escapeHtml(title.accent_from)};--to:${escapeHtml(title.accent_to)}"><span>${escapeHtml(title.genre)}</span><b>${escapeHtml(title.name)}</b></article>`).join("");
  el("injectTitle").innerHTML = titles.map(title => `<option value="${escapeHtml(title.id)}">${escapeHtml(title.name)}</option>`).join("");
  el("catalogGrid").dataset.rendered = "true";
}

function openIncident(id) {
  const incident = state.incidents.get(id); if (!incident) return;
  const pending = incident.status === "pending_approval";
  const trace = incident.agent_trace.map((step, index) => `<div class="trace-step"><i>0${index + 1}</i><div><b>${escapeHtml(step.agent)}</b><small>${escapeHtml(step.summary)}</small></div><time>${step.duration_ms}ms</time></div>`).join("");
  el("incidentDetail").innerHTML = `<div class="detail-top"><div><span class="section-label">${escapeHtml(incident.impact.severity.toUpperCase())} INCIDENT · ${escapeHtml(incident.anomaly.region.toUpperCase())}</span><h2>${escapeHtml(incident.anomaly.title_name)}</h2><p>${escapeHtml(incident.anomaly.kind.replaceAll("_", " "))} · ${escapeHtml(incident.root_cause.primary_value)}</p></div><button class="detail-close" aria-label="Close">×</button></div><div class="impact-row"><div><span>VIEWER-HOURS</span><b>${fmt.format(incident.impact.lost_viewer_hours)}</b></div><div><span>AFFECTED SESSIONS</span><b>${fmt.format(incident.impact.affected_sessions)}</b></div><div><span>EST. REVENUE</span><b>${money.format(incident.impact.estimated_revenue_loss_usd)}</b></div></div><div class="brief-box"><span>EXECUTIVE BRIEF</span><p>${escapeHtml(incident.executive_brief)}</p></div><div class="trace"><span>AGENT TRACE</span>${trace}</div><div class="decision-box"><b>${pending ? "PENDING HUMAN DECISION" : escapeHtml(incident.status.toUpperCase())}</b><p>${escapeHtml(incident.recommended_action)}</p>${pending ? `<div class="decision-actions"><button class="danger-button" data-decision="dismiss">Dismiss</button><button class="primary-button" data-decision="approve">Approve recommendation</button></div>` : `<p>${escapeHtml(incident.decision_note || "Decision recorded without an operator note.")}</p>`}</div>`;
  el("incidentDetail").querySelector(".detail-close").addEventListener("click", () => el("incidentDialog").close());
  el("incidentDetail").querySelectorAll("[data-decision]").forEach(button => button.addEventListener("click", () => decide(id, button.dataset.decision)));
  el("incidentDialog").showModal();
}

async function decide(id, decision) {
  try {
    await api(`/api/incidents/${id}/${decision}`, { method: "POST", headers: headers(), body: JSON.stringify({ note: `${decision === "approve" ? "Approved" : "Dismissed"} by the human operator in the WatchTower dashboard.` }) });
    el("incidentDialog").close(); toast(`Incident ${decision === "approve" ? "approved" : "dismissed"}. No downstream action executed.`); await refresh();
  } catch (error) { handleAdminError(error); }
}

async function inject(event) {
  event.preventDefault();
  const submit = event.submitter; if (submit?.value === "cancel") return;
  const kind = new FormData(event.currentTarget).get("kind");
  const payload = { kind, title_id: el("injectTitle").value, region: el("injectRegion").value, duration_cycles: 4, magnitude: .8 };
  try {
    await api("/api/admin/inject", { method: "POST", headers: headers(), body: JSON.stringify(payload) });
    el("injectDialog").close(); toast("Synthetic incident armed. Agents are watching the next live cycles.");
    for (let i = 0; i < 3; i++) { await api("/api/admin/tick", { method: "POST", headers: headers(), body: "{}" }); }
    await refresh();
  } catch (error) { handleAdminError(error); }
}

function handleAdminError(error) { if (/token/i.test(error.message)) el("settingsDialog").showModal(); toast(error.message, true); }
function relativeTime(value) { const seconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000); if (seconds < 10) return "just now"; if (seconds < 60) return `${Math.floor(seconds)}s ago`; return `${Math.floor(seconds / 60)}m ago`; }

el("openInjectButton").addEventListener("click", () => el("injectDialog").showModal());
el("settingsButton").addEventListener("click", () => { el("adminToken").value = token(); el("settingsDialog").showModal(); });
el("injectForm").addEventListener("submit", inject);
el("useDemoKey")?.addEventListener("click", () => { el("adminToken").value = el("demoKey").textContent.trim(); });
el("settingsForm").addEventListener("submit", event => { event.preventDefault(); sessionStorage.setItem("watchtower-admin-token", el("adminToken").value.trim()); el("settingsDialog").close(); toast("Operator key saved for this browser session."); });
el("incidentDialog").addEventListener("click", event => { if (event.target === el("incidentDialog")) el("incidentDialog").close(); });
refresh(); setInterval(refresh, 15000);
