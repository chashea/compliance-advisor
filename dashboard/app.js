/* ═══════════════════════════════════════════════════════════════════════════
   Compliance Advisor Dashboard — Microsoft Graph Security Data
   Fetches Secure Score, Controls, Alerts, Incidents, Risky Users, Service Health.
   ═══════════════════════════════════════════════════════════════════════════ */

// ── Configuration ───────────────────────────────────────────────────────────
const CONFIG = {
  apiBase: window.COMPLIANCE_API_BASE || "/api/advisor",
  functionKey: window.COMPLIANCE_API_KEY || "",
};

// ── Chart.js global defaults ────────────────────────────────────────────────
Chart.defaults.color = "#8b8fa3";
Chart.defaults.borderColor = "rgba(45,48,64,.6)";
Chart.defaults.font.family =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';

const CHART_COLORS = {
  blue:    "#4f8ff7",
  green:   "#34d399",
  red:     "#f87171",
  yellow:  "#fbbf24",
  purple:  "#a78bfa",
  teal:    "#2dd4bf",
  pink:    "#f472b6",
  orange:  "#fb923c",
};
const PALETTE = Object.values(CHART_COLORS);

// ── State ───────────────────────────────────────────────────────────────────
let charts = {};
let currentData = {};
let demoMode = false;
let sortState = {};

// ── DOM References ──────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── API Client ──────────────────────────────────────────────────────────────
async function api(action, body = {}) {
  const url = `${CONFIG.apiBase}/${action}`;
  const headers = { "Content-Type": "application/json" };
  if (CONFIG.functionKey) headers["x-functions-key"] = CONFIG.functionKey;
  const resp = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    throw new Error(err.error || `API error: ${resp.status}`);
  }
  return resp.json();
}

// ── Status Indicator ────────────────────────────────────────────────────────
function setStatus(state, text) {
  const dot = $(".status-bar__dot");
  const txt = $("#status-text");
  dot.className = "status-bar__dot";
  if (state === "ok") dot.classList.add("status-bar__dot--ok");
  if (state === "error") dot.classList.add("status-bar__dot--err");
  txt.textContent = text;
}

function setLoadingSkeleton(show) {
  const sk = $("#loading-skeleton");
  const main = $(".main-content");
  if (!sk || !main) return;
  if (show) {
    sk.hidden = false;
    main.style.visibility = "hidden";
    main.style.minHeight = "400px";
  } else {
    sk.hidden = true;
    main.style.visibility = "";
    main.style.minHeight = "";
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// DEMO DATA
// ═════════════════════════════════════════════════════════════════════════════

function generateDemoData() {
  const categories = ["Identity", "Data", "Device", "Apps", "Infrastructure"];
  const services = ["Exchange Online", "SharePoint Online", "Teams", "OneDrive",
    "Azure Active Directory", "Microsoft Defender", "Intune", "Power Platform",
    "Dynamics 365", "Microsoft 365 Apps"];

  const controlScores = [];
  for (let i = 0; i < 40; i++) {
    const pct = Math.random() * 100;
    controlScores.push({
      control_name: `Control-${i + 1}`,
      category: categories[i % categories.length],
      score: +(pct * 0.1).toFixed(1),
      score_pct: +pct.toFixed(1),
      implementation_status: pct === 100 ? "Implemented" : pct > 50 ? "Partial" : "NotImplemented",
      display_name: "Demo Tenant",
    });
  }

  const categoryRollup = categories.map(c => {
    const inCat = controlScores.filter(cs => cs.category === c);
    return {
      category: c,
      total_controls: inCat.length,
      fully_implemented: inCat.filter(x => x.score_pct === 100).length,
      not_implemented: inCat.filter(x => x.score_pct === 0).length,
      avg_score_pct: +(inCat.reduce((s, x) => s + x.score_pct, 0) / inCat.length).toFixed(1),
      total_score: +(inCat.reduce((s, x) => s + x.score, 0)).toFixed(1),
    };
  });

  const opportunities = [];
  for (let i = 0; i < 10; i++) {
    opportunities.push({
      title: `Enable MFA for ${categories[i % 5]} accounts`,
      control_id: `ctrl-${i}`,
      service: services[i % services.length],
      category: categories[i % categories.length],
      max_score: +(10 - i * 0.5).toFixed(1),
      tier: i < 3 ? "Tier1" : "Tier2",
      implementation_cost: i < 3 ? "Low" : "Medium",
      user_impact: i < 5 ? "Low" : "Medium",
    });
  }

  const alerts = [
    { title: "Suspicious sign-in activity", severity: "high", status: "new", category: "Identity", service_source: "Azure AD", created: "2026-03-07" },
    { title: "Impossible travel detected", severity: "medium", status: "inProgress", category: "Identity", service_source: "Azure AD", created: "2026-03-06" },
    { title: "Malware detected on endpoint", severity: "high", status: "new", category: "Endpoint", service_source: "Defender", created: "2026-03-05" },
  ];

  const severityBreakdown = [
    { severity: "high", total: 2, active: 2 },
    { severity: "medium", total: 1, active: 1 },
    { severity: "low", total: 0, active: 0 },
  ];

  const riskyUsers = [
    { user_display_name: "John Doe", risk_level: "high", risk_state: "atRisk" },
    { user_display_name: "Jane Smith", risk_level: "medium", risk_state: "confirmedCompromised" },
  ];

  const serviceHealth = services.map(s => ({
    service_name: s,
    status: Math.random() > 0.15 ? "serviceOperational" : "serviceDegradation",
    display_name: "Demo Tenant",
  }));

  return {
    overview: {
      tenants: [{
        tenant_id: "demo-tenant-1",
        display_name: "Demo Tenant",
        department: "IT",
        secure_score: 413.9,
        max_score: 893.0,
        score_pct: 46.35,
        active_user_count: 150,
        licensed_user_count: 200,
        controls_total: 121,
        controls_implemented: 58,
        snapshot_date: new Date().toISOString().slice(0, 10),
      }],
      alert_summary: { high_alerts: 2, medium_alerts: 1, low_alerts: 0, active_alerts: 3, total_alerts: 3 },
      incident_summary: { total_incidents: 1, active_incidents: 1, high_incidents: 0 },
      risky_user_summary: { total_risky_users: 2, high_risk_users: 1 },
      service_health_summary: { total_services: 10, healthy_services: 8 },
    },
    scoreTrend: {
      daily_scores: [],
      trend: [],
    },
    controls: {
      control_scores: controlScores,
      categories: categoryRollup,
      opportunities: opportunities,
    },
    alerts: {
      alerts: alerts,
      severity_breakdown: severityBreakdown,
    },
    security: {
      incidents: [{ display_name: "Multi-stage incident", severity: "medium", status: "active", classification: "truePositive", created: "2026-03-06" }],
      risky_users: riskyUsers,
    },
    serviceHealth: {
      services: serviceHealth,
    },
  };
}

// ═════════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ═════════════════════════════════════════════════════════════════════════════

async function loadData() {
  setLoadingSkeleton(true);
  const dept = $("#department-filter")?.value || "";
  const days = parseInt($("#days-filter")?.value || "30");
  const body = {};
  if (dept) body.department = dept;
  body.days = days;

  try {
    if (demoMode) {
      currentData = generateDemoData();
    } else {
      const [overview, scoreTrend, controls, alerts, security, serviceHealth] = await Promise.all([
        api("overview", body),
        api("score-trend", body),
        api("controls", body),
        api("alerts", body),
        api("security", body),
        api("service-health", body),
      ]);
      currentData = { overview, scoreTrend, controls, alerts, security, serviceHealth };
    }

    renderAll();
    const tenantCount = currentData.overview?.tenants?.length || 0;
    setStatus("ok", demoMode ? "Demo mode" : `Connected — ${tenantCount} tenant${tenantCount !== 1 ? "s" : ""}`);
  } catch (err) {
    console.error("Load error:", err);
    setStatus("error", `Error: ${err.message}`);
  } finally {
    setLoadingSkeleton(false);
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// RENDERING
// ═════════════════════════════════════════════════════════════════════════════

function renderAll() {
  renderKPIs();
  renderTrendChart();
  renderCategoryChart();
  renderAlertChart();
  renderOpportunities();
  renderControlScores();
  renderAlerts();
  renderRiskyUsers();
  renderServiceHealth();
  populateDepartments();
}

function renderKPIs() {
  const ov = currentData.overview || {};
  const tenants = ov.tenants || [];
  const alertSummary = ov.alert_summary || {};
  const healthSummary = ov.service_health_summary || {};

  if (tenants.length > 0) {
    const t = tenants[0];
    $("#kpi-score").textContent = `${t.secure_score?.toFixed(1) || 0}/${t.max_score?.toFixed(0) || 0}`;
    $("#kpi-pct").textContent = `${t.score_pct?.toFixed(1) || 0}%`;
    $("#kpi-controls").textContent = `${t.controls_implemented || 0}/${t.controls_total || 0}`;
  }

  $("#kpi-tenants").textContent = tenants.length;
  $("#kpi-alerts").textContent = alertSummary.active_alerts || 0;
  const healthy = healthSummary.healthy_services || 0;
  const total = healthSummary.total_services || 0;
  $("#kpi-health").textContent = `${healthy}/${total}`;
}

function renderTrendChart() {
  const data = currentData.scoreTrend || {};
  const daily = data.daily_scores || [];

  if (charts.trend) charts.trend.destroy();

  const labels = daily.map(d => d.snapshot_date);
  const scores = daily.map(d => d.score_pct);

  charts.trend = new Chart($("#trend-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Secure Score %",
        data: scores,
        borderColor: CHART_COLORS.blue,
        backgroundColor: "rgba(79,143,247,0.1)",
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { min: 0, max: 100, ticks: { callback: v => v + "%" } } },
      plugins: { legend: { display: false } },
    },
  });
}

function renderCategoryChart() {
  const cats = currentData.controls?.categories || [];
  if (charts.category) charts.category.destroy();

  charts.category = new Chart($("#category-chart"), {
    type: "bar",
    data: {
      labels: cats.map(c => c.category),
      datasets: [{
        label: "Avg Score %",
        data: cats.map(c => c.avg_score_pct),
        backgroundColor: PALETTE,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      indexAxis: "y",
      scales: { x: { min: 0, max: 100, ticks: { callback: v => v + "%" } } },
      plugins: { legend: { display: false } },
    },
  });
}

function renderAlertChart() {
  const breakdown = currentData.alerts?.severity_breakdown || [];
  if (charts.alert) charts.alert.destroy();

  const labels = breakdown.map(b => b.severity);
  const totals = breakdown.map(b => b.total);
  const colors = labels.map(l => {
    if (l === "high") return CHART_COLORS.red;
    if (l === "medium") return CHART_COLORS.yellow;
    if (l === "low") return CHART_COLORS.green;
    return CHART_COLORS.purple;
  });

  charts.alert = new Chart($("#alert-chart"), {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: totals, backgroundColor: colors }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
      },
    },
  });
}

function renderOpportunities() {
  const opps = currentData.controls?.opportunities || [];
  const tbody = $("#opportunities-table tbody");
  tbody.innerHTML = opps.slice(0, 15).map(o => `
    <tr>
      <td>${esc(o.title)}</td>
      <td>${esc(o.service)}</td>
      <td>${esc(o.category)}</td>
      <td><strong>${o.max_score}</strong></td>
      <td>${esc(o.tier)}</td>
      <td>${esc(o.implementation_cost)}</td>
      <td>${esc(o.user_impact)}</td>
    </tr>
  `).join("");
}

function renderControlScores() {
  const scores = currentData.controls?.control_scores || [];
  const tbody = $("#controls-table tbody");
  tbody.innerHTML = scores.map(s => `
    <tr>
      <td>${esc(s.control_name)}</td>
      <td>${esc(s.category)}</td>
      <td>${s.score}</td>
      <td>${scoreBadge(s.score_pct)}</td>
      <td>${statusBadge(s.implementation_status)}</td>
    </tr>
  `).join("");
}

function renderAlerts() {
  const alerts = currentData.alerts?.alerts || [];
  const tbody = $("#alerts-table tbody");
  if (alerts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="placeholder-text">No security alerts</td></tr>';
    return;
  }
  tbody.innerHTML = alerts.map(a => `
    <tr>
      <td>${esc(a.title)}</td>
      <td>${severityBadge(a.severity)}</td>
      <td>${statusBadge(a.status)}</td>
      <td>${esc(a.category)}</td>
      <td>${esc(a.service_source)}</td>
      <td>${esc(a.created?.slice(0, 10) || "")}</td>
    </tr>
  `).join("");
}

function renderRiskyUsers() {
  const users = currentData.security?.risky_users || [];
  const tbody = $("#risky-users-table tbody");
  if (users.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="placeholder-text">No risky users detected</td></tr>';
    return;
  }
  tbody.innerHTML = users.map(u => `
    <tr>
      <td>${esc(u.user_display_name)}</td>
      <td>${severityBadge(u.risk_level)}</td>
      <td>${esc(u.risk_state)}</td>
    </tr>
  `).join("");
}

function renderServiceHealth() {
  const services = currentData.serviceHealth?.services || [];
  const grid = $("#service-health-grid");
  if (services.length === 0) {
    grid.innerHTML = '<p class="placeholder-text">No service health data</p>';
    return;
  }
  grid.innerHTML = services.map(s => {
    const isHealthy = s.status === "serviceOperational";
    const dot = isHealthy ? "status-bar__dot--ok" : "status-bar__dot--err";
    const label = isHealthy ? "Operational" : s.status.replace(/([A-Z])/g, " $1").trim();
    return `
      <div class="service-tile ${isHealthy ? "" : "service-tile--degraded"}">
        <span class="status-bar__dot ${dot}"></span>
        <span class="service-tile__name">${esc(s.service_name)}</span>
        <span class="service-tile__status">${label}</span>
      </div>
    `;
  }).join("");
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function scoreBadge(pct) {
  let cls = "badge--red";
  if (pct >= 80) cls = "badge--green";
  else if (pct >= 50) cls = "badge--yellow";
  return `<span class="badge ${cls}">${pct?.toFixed(1) || 0}%</span>`;
}

function severityBadge(sev) {
  const s = (sev || "").toLowerCase();
  let cls = "badge--blue";
  if (s === "high") cls = "badge--red";
  else if (s === "medium") cls = "badge--yellow";
  else if (s === "low") cls = "badge--green";
  return `<span class="badge ${cls}">${esc(sev)}</span>`;
}

function statusBadge(status) {
  const s = (status || "").toLowerCase();
  let cls = "badge--blue";
  if (s === "resolved" || s === "implemented" || s === "passed") cls = "badge--green";
  else if (s === "new" || s === "notimplemented" || s === "failed") cls = "badge--red";
  else if (s === "inprogress" || s === "partial" || s === "planned") cls = "badge--yellow";
  return `<span class="badge ${cls}">${esc(status)}</span>`;
}

function populateDepartments() {
  const tenants = currentData.overview?.tenants || [];
  const depts = [...new Set(tenants.map(t => t.department).filter(Boolean))];
  const sel = $("#department-filter");
  const current = sel.value;
  // Keep "All Departments" option
  while (sel.options.length > 1) sel.remove(1);
  depts.sort().forEach(d => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    sel.add(opt);
  });
  sel.value = current;
}

// ── Sortable Tables ─────────────────────────────────────────────────────────

function initSortableTables() {
  $$(".data-table--sortable th[data-sort]").forEach(th => {
    th.style.cursor = "pointer";
    th.addEventListener("click", () => {
      const table = th.closest("table");
      const key = th.dataset.sort;
      const isNum = th.hasAttribute("data-sort-num");
      const id = table.id;
      const prev = sortState[id];
      const dir = prev?.key === key ? -prev.dir : 1;
      sortState[id] = { key, dir };

      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {
        const idx = Array.from(th.parentElement.children).indexOf(th);
        let va = a.children[idx]?.textContent.trim() || "";
        let vb = b.children[idx]?.textContent.trim() || "";
        if (isNum) {
          va = parseFloat(va.replace(/[^0-9.-]/g, "")) || 0;
          vb = parseFloat(vb.replace(/[^0-9.-]/g, "")) || 0;
          return (va - vb) * dir;
        }
        return va.localeCompare(vb) * dir;
      });
      rows.forEach(r => tbody.appendChild(r));

      table.querySelectorAll("th[data-sort]").forEach(h => {
        const icon = h.querySelector(".sort-icon");
        if (icon) icon.textContent = h === th ? (dir === 1 ? " ▲" : " ▼") : "";
      });
    });
  });
}

// ── Briefing ────────────────────────────────────────────────────────────────

function initBriefing() {
  const btn = $("#generate-briefing-btn");
  const copyBtn = $("#copy-briefing-btn");
  const content = $("#briefing-content");

  btn?.addEventListener("click", async () => {
    btn.disabled = true;
    btn.textContent = "Generating...";
    content.innerHTML = '<p class="placeholder-text">Generating briefing...</p>';
    try {
      const dept = $("#department-filter")?.value || "";
      const body = {};
      if (dept) body.department = dept;
      const data = await api("briefing", body);
      content.innerHTML = `<div class="briefing-text">${formatBriefing(data.briefing)}</div>`;
      copyBtn.disabled = false;
    } catch (err) {
      content.innerHTML = `<p class="placeholder-text" style="color:var(--red)">Error: ${esc(err.message)}</p>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Generate Briefing";
    }
  });

  copyBtn?.addEventListener("click", () => {
    const text = content.textContent;
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.textContent = "Copied!";
      setTimeout(() => (copyBtn.textContent = "Copy"), 2000);
    });
  });
}

function formatBriefing(text) {
  return text
    .replace(/\n/g, "<br>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>");
}

// ── Ask Advisor ─────────────────────────────────────────────────────────────

function initAdvisor() {
  const input = $("#ask-input");
  const btn = $("#ask-btn");
  const resp = $("#ask-response");

  async function askQuestion(question) {
    if (!question.trim()) return;
    resp.innerHTML = '<p class="placeholder-text">Thinking...</p>';
    try {
      const dept = $("#department-filter")?.value || "";
      const body = { question };
      if (dept) body.department = dept;
      const data = await api("ask", body);
      resp.innerHTML = `<div class="briefing-text">${formatBriefing(data.answer)}</div>`;
    } catch (err) {
      resp.innerHTML = `<p style="color:var(--red)">${esc(err.message)}</p>`;
    }
  }

  btn?.addEventListener("click", () => askQuestion(input.value));
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") askQuestion(input.value);
  });

  $$(".chip[data-question]").forEach(chip => {
    chip.addEventListener("click", () => {
      input.value = chip.dataset.question;
      askQuestion(chip.dataset.question);
    });
  });
}

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", () => {
  const demoToggle = $("#demo-mode-toggle");
  demoToggle?.addEventListener("change", () => {
    demoMode = demoToggle.checked;
    loadData();
  });

  $("#refresh-btn")?.addEventListener("click", loadData);
  $("#department-filter")?.addEventListener("change", loadData);
  $("#days-filter")?.addEventListener("change", loadData);

  initSortableTables();
  initBriefing();
  initAdvisor();
  loadData();
});
