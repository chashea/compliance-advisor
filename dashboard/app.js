/* ═══════════════════════════════════════════════════════════════════════════
   Compliance Advisor Dashboard — Microsoft Graph Compliance Workload Data
   Fetches eDiscovery, Labels, Audit, DLP, Governance data.
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
const DEFAULT_DAYS = 30;

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
    const message = err?.error || `API error: ${resp.status}`;
    throw new Error(err?.code ? `[${err.code}] ${message}` : message);
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
  const ediscoveryCases = [
    { display_name: "Investigation Alpha", status: "active", custodian_count: 5, created: "2026-02-01", tenant_name: "Demo Tenant" },
    { display_name: "HR Review 2026", status: "closed", custodian_count: 3, created: "2025-11-15", tenant_name: "Demo Tenant" },
    { display_name: "Litigation Hold - Project X", status: "active", custodian_count: 12, created: "2026-01-10", tenant_name: "Demo Tenant" },
  ];

  const sensitivityLabels = [
    { name: "Public", priority: 0, is_active: true, color: "#00cc00", tenant_name: "Demo Tenant" },
    { name: "Internal", priority: 1, is_active: true, color: "#ffcc00", tenant_name: "Demo Tenant" },
    { name: "Confidential", priority: 2, is_active: true, color: "#ff6600", tenant_name: "Demo Tenant" },
    { name: "Highly Confidential", priority: 3, is_active: true, color: "#cc0000", tenant_name: "Demo Tenant" },
    { name: "Restricted (Legacy)", priority: 4, is_active: false, color: "#990000", tenant_name: "Demo Tenant" },
  ];

  const retentionLabels = [
    { display_name: "7-Year Retention", retention_duration: "P2555D", is_in_use: true, status: "active" },
    { display_name: "3-Year Retention", retention_duration: "P1095D", is_in_use: true, status: "active" },
    { display_name: "Permanent Hold", retention_duration: "unlimited", is_in_use: false, status: "active" },
  ];

  const dlpAlerts = [
    { title: "SSN detected in email", severity: "high", status: "new", policy_name: "PII Protection", created: "2026-03-07", tenant_name: "Demo Tenant" },
    { title: "Credit card in Teams message", severity: "medium", status: "inProgress", policy_name: "Financial Data", created: "2026-03-06", tenant_name: "Demo Tenant" },
    { title: "Driver license in SharePoint", severity: "low", status: "resolved", policy_name: "PII Protection", created: "2026-03-05", tenant_name: "Demo Tenant" },
  ];

  const dlpSeverityBreakdown = [
    { severity: "high", total: 1, active: 1 },
    { severity: "medium", total: 1, active: 1 },
    { severity: "low", total: 1, active: 0 },
  ];

  const auditRecords = [
    { operation: "SensitivityLabelApplied", service: "SharePoint", user_id: "admin@demo.onmicrosoft.com", created: "2026-03-07T14:22:00Z" },
    { operation: "DLPRuleMatch", service: "Exchange", user_id: "user1@demo.onmicrosoft.com", created: "2026-03-07T12:05:00Z" },
    { operation: "RetentionLabelApplied", service: "OneDrive", user_id: "admin@demo.onmicrosoft.com", created: "2026-03-07T09:30:00Z" },
  ];

  const governanceScopes = [
    { scope_type: "dlpPolicy", execution_mode: "enforce", locations: "Exchange, SharePoint, OneDrive" },
    { scope_type: "retentionPolicy", execution_mode: "enforce", locations: "Exchange, SharePoint" },
  ];

  return {
    overview: {
      tenants: [{ tenant_id: "demo-tenant-1", display_name: "Demo Tenant", department: "IT" }],
      ediscovery_summary: { total_cases: 3, active_cases: 2 },
      labels_summary: { sensitivity_labels: 5, retention_labels: 3 },
      dlp_summary: { total_dlp_alerts: 3, high_alerts: 1, medium_alerts: 1, active_alerts: 2 },
      audit_summary: { total_records: 3 },
    },
    ediscovery: { cases: ediscoveryCases, status_breakdown: [{ status: "active", total: 2 }, { status: "closed", total: 1 }] },
    labels: { sensitivity_labels: sensitivityLabels, retention_labels: retentionLabels, retention_events: [] },
    dlp: { alerts: dlpAlerts, severity_breakdown: dlpSeverityBreakdown, policy_breakdown: [{ policy_name: "PII Protection", total: 2 }, { policy_name: "Financial Data", total: 1 }] },
    audit: { records: auditRecords, service_breakdown: [{ service: "SharePoint", total: 1 }, { service: "Exchange", total: 1 }, { service: "OneDrive", total: 1 }], operation_breakdown: [] },
    governance: { scopes: governanceScopes },
    irm: {
      alerts: [
        { title: "Unusual file download volume", severity: "high", status: "new", policy_name: "Data Theft", created: "2026-03-07", tenant_name: "Demo Tenant" },
        { title: "Sequence of exfiltration activities", severity: "medium", status: "inProgress", policy_name: "Data Leaks", created: "2026-03-06", tenant_name: "Demo Tenant" },
      ],
      severity_breakdown: [
        { severity: "high", total: 1, active: 1 },
        { severity: "medium", total: 1, active: 1 },
      ],
    },
    subjectRights: {
      requests: [
        { display_name: "DSAR - John Doe", request_type: "access", status: "active", created: "2026-03-01", tenant_name: "Demo Tenant" },
        { display_name: "DSAR - Jane Smith", request_type: "delete", status: "closed", created: "2026-02-15", tenant_name: "Demo Tenant" },
      ],
      status_breakdown: [{ status: "active", total: 1 }, { status: "closed", total: 1 }],
    },
    commCompliance: {
      policies: [
        { display_name: "Offensive Language Policy", policy_type: "offensive_language", status: "active", review_pending_count: 5, tenant_name: "Demo Tenant" },
        { display_name: "Regulatory Compliance", policy_type: "regulatory", status: "active", review_pending_count: 0, tenant_name: "Demo Tenant" },
      ],
    },
    infoBarriers: {
      policies: [
        { display_name: "Research - Trading Wall", state: "active", segments_applied: "Research, Trading", tenant_name: "Demo Tenant" },
        { display_name: "HR - Finance Barrier", state: "active", segments_applied: "HR, Finance", tenant_name: "Demo Tenant" },
      ],
    },
    trend: { trend: [] },
    actions: {
      secure_score: { current_score: 62.5, max_score: 100, score_date: "2026-03-08" },
      actions: [
        { rank: 1, title: "Enable MFA for all users", control_category: "Identity", max_score: 10, implementation_cost: "Low", user_impact: "Moderate", tier: "Core", service: "Microsoft Entra ID", threats: "Account Breach", state: "Default", tenant_name: "Demo Tenant" },
        { rank: 5, title: "Apply Data Loss Prevention policies", control_category: "Data", max_score: 20, implementation_cost: "Moderate", user_impact: "Moderate", tier: "Advanced", service: "IP", threats: "Data Exfiltration, Data Spillage", state: "Default", tenant_name: "Demo Tenant" },
        { rank: 12, title: "Enable audit logging", control_category: "Data", max_score: 5, implementation_cost: "Low", user_impact: "Low", tier: "Core", service: "Exchange", threats: "Data Exfiltration", state: "Default", tenant_name: "Demo Tenant" },
        { rank: 20, title: "Configure device compliance policies", control_category: "Device", max_score: 15, implementation_cost: "High", user_impact: "High", tier: "Defense in Depth", service: "Intune", threats: "Elevation of Privilege", state: "Default", tenant_name: "Demo Tenant" },
      ],
      category_breakdown: [
        { control_category: "Data", total: 2, total_max_score: 25 },
        { control_category: "Device", total: 1, total_max_score: 15 },
        { control_category: "Identity", total: 1, total_max_score: 10 },
      ],
    },
  };
}

// ═════════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ═════════════════════════════════════════════════════════════════════════════

async function loadData() {
  setLoadingSkeleton(true);
  const { dept, days } = getCurrentFilters();
  updateFilterStateUI();
  const body = {};
  if (dept) body.department = dept;
  body.days = days;

  try {
    if (demoMode) {
      currentData = generateDemoData();
    } else {
      const [overview, ediscovery, labels, dlp, irm, subjectRights, commCompliance, infoBarriers, audit, governance, trend, actions] = await Promise.all([
        api("overview", body),
        api("ediscovery", body),
        api("labels", body),
        api("dlp", body),
        api("irm", body),
        api("subject-rights", body),
        api("comm-compliance", body),
        api("info-barriers", body),
        api("audit", body),
        api("governance", body),
        api("trend", body),
        api("actions", body),
      ]);
      currentData = { overview, ediscovery, labels, dlp, irm, subjectRights, commCompliance, infoBarriers, audit, governance, trend, actions };
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
  renderDLPChart();
  renderEdiscovery();
  renderSensitivityLabels();
  renderRetentionLabels();
  renderDLPAlerts();
  renderIRMAlerts();
  renderSubjectRights();
  renderCommCompliance();
  renderInfoBarriers();
  renderAuditRecords();
  renderGovernance();
  renderImprovementActions();
  populateDepartments();
}

function renderKPIs() {
  const ov = currentData.overview || {};
  const tenants = ov.tenants || [];
  const edSummary = ov.ediscovery_summary || {};
  const dlpSummary = ov.dlp_summary || {};

  $("#kpi-tenants").textContent = tenants.length;
  $("#kpi-ediscovery").textContent = `${edSummary.active_cases || 0} active`;
  $("#kpi-dlp").textContent = `${dlpSummary.active_alerts || 0} active`;
  const irmAlerts = currentData.irm?.alerts || [];
  const irmActive = irmAlerts.filter(a => (a.status || "").toLowerCase() !== "resolved").length;
  $("#kpi-irm").textContent = `${irmActive} active`;
}

function renderTrendChart() {
  const data = currentData.trend || {};
  const trend = data.trend || [];

  if (charts.trend) charts.trend.destroy();

  const labels = trend.map(d => d.snapshot_date);

  charts.trend = new Chart($("#trend-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "eDiscovery", data: trend.map(d => d.ediscovery_cases), borderColor: CHART_COLORS.blue, tension: 0.3 },
        { label: "DLP Alerts", data: trend.map(d => d.dlp_alerts), borderColor: CHART_COLORS.red, tension: 0.3 },
        { label: "Audit Records", data: trend.map(d => d.audit_records), borderColor: CHART_COLORS.green, tension: 0.3 },
        { label: "Sensitivity Labels", data: trend.map(d => d.sensitivity_labels), borderColor: CHART_COLORS.purple, tension: 0.3 },
        { label: "Retention Labels", data: trend.map(d => d.retention_labels), borderColor: CHART_COLORS.orange, tension: 0.3 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { min: 0 } },
      plugins: { legend: { position: "bottom" } },
    },
  });
}

function renderDLPChart() {
  const breakdown = currentData.dlp?.severity_breakdown || [];
  if (charts.dlp) charts.dlp.destroy();

  const labels = breakdown.map(b => b.severity);
  const totals = breakdown.map(b => b.total);
  const grand = totals.reduce((a, b) => a + b, 0);
  const colors = labels.map(l => {
    if (l === "high") return "rgba(248,113,113,.6)";
    if (l === "medium") return "rgba(251,191,36,.55)";
    if (l === "low") return "rgba(52,211,153,.55)";
    return "rgba(167,139,250,.55)";
  });

  charts.dlp = new Chart($("#dlp-chart"), {
    type: "doughnut",
    data: {
      labels: labels.map((l, i) => {
        const pct = grand > 0 ? Math.round((totals[i] / grand) * 100) : 0;
        return `${l} ${pct}%`;
      }),
      datasets: [{ data: totals, backgroundColor: colors }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const val = ctx.parsed;
              const pct = grand > 0 ? Math.round((val / grand) * 100) : 0;
              return ` ${ctx.label}: ${val} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

function renderEdiscovery() {
  const cases = currentData.ediscovery?.cases || [];
  const tbody = $("#ediscovery-table tbody");
  if (cases.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="placeholder-text">No eDiscovery cases</td></tr>';
    return;
  }
  tbody.innerHTML = cases.map(c => `
    <tr>
      <td>${esc(c.display_name)}</td>
      <td>${statusBadge(c.status)}</td>
      <td>${c.custodian_count || 0}</td>
      <td>${esc(c.created?.slice(0, 10) || "")}</td>
      <td>${esc(c.tenant_name)}</td>
    </tr>
  `).join("");
}

function renderSensitivityLabels() {
  const labels = currentData.labels?.sensitivity_labels || [];
  const tbody = $("#sensitivity-table tbody");
  if (labels.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No sensitivity labels</td></tr>';
    return;
  }
  tbody.innerHTML = labels.map(l => `
    <tr>
      <td>${l.color ? `<span style="display:inline-block;width:12px;height:12px;border-radius:2px;background:${esc(l.color)};margin-right:6px;vertical-align:middle"></span>` : ""}${esc(l.name)}</td>
      <td>${l.priority}</td>
      <td>${l.is_active ? '<span class="badge badge--green">Active</span>' : '<span class="badge badge--red">Inactive</span>'}</td>
      <td>${esc(l.tenant_name)}</td>
    </tr>
  `).join("");
}

function renderRetentionLabels() {
  const labels = currentData.labels?.retention_labels || [];
  const tbody = $("#retention-table tbody");
  if (labels.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No retention labels</td></tr>';
    return;
  }
  tbody.innerHTML = labels.map(l => `
    <tr>
      <td>${esc(l.display_name)}</td>
      <td>${esc(l.retention_duration)}</td>
      <td>${l.is_in_use ? '<span class="badge badge--green">Yes</span>' : '<span class="badge badge--yellow">No</span>'}</td>
      <td>${statusBadge(l.status)}</td>
    </tr>
  `).join("");
}

function renderDLPAlerts() {
  const alerts = currentData.dlp?.alerts || [];
  populateDLPFilters(alerts);
  applyDLPFilters();
}

function populateDLPFilters(alerts) {
  const statusSel = $("#dlp-status-filter");
  const tenantSel = $("#dlp-tenant-filter");
  if (!statusSel || !tenantSel) return;

  const curStatus = statusSel.value;
  const curTenant = tenantSel.value;

  const statuses = [...new Set(alerts.map(a => a.status).filter(Boolean))].sort();
  const tenants = [...new Set(alerts.map(a => a.tenant_name).filter(Boolean))].sort();

  while (statusSel.options.length > 1) statusSel.remove(1);
  statuses.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = s;
    statusSel.add(opt);
  });
  statusSel.value = curStatus;

  while (tenantSel.options.length > 1) tenantSel.remove(1);
  tenants.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    tenantSel.add(opt);
  });
  tenantSel.value = curTenant;
}

function applyDLPFilters() {
  const alerts = currentData.dlp?.alerts || [];
  const sevFilter = $("#dlp-severity-filter")?.value || "";
  const statusFilter = $("#dlp-status-filter")?.value || "";
  const tenantFilter = $("#dlp-tenant-filter")?.value || "";

  const filtered = alerts.filter(a => {
    if (sevFilter && (a.severity || "").toLowerCase() !== sevFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    if (tenantFilter && a.tenant_name !== tenantFilter) return false;
    return true;
  });

  const tbody = $("#dlp-table tbody");
  if (filtered.length === 0) {
    const msg = alerts.length === 0 ? "No DLP alerts" : "No alerts match the selected filters";
    tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text">${msg}</td></tr>`;
  } else {
    tbody.innerHTML = filtered.map(a => `
      <tr>
        <td>${esc(a.title)}</td>
        <td>${severityBadge(a.severity)}</td>
        <td>${statusBadge(a.status)}</td>
        <td>${esc(a.policy_name)}</td>
        <td>${esc(a.created?.slice(0, 10) || "")}</td>
        <td>${esc(a.tenant_name)}</td>
      </tr>
    `).join("");
  }

  updateDLPFilterState();
}

function updateDLPFilterState() {
  const sevSel = $("#dlp-severity-filter");
  const statusSel = $("#dlp-status-filter");
  const tenantSel = $("#dlp-tenant-filter");
  const clearBtn = $("#dlp-clear-filters");
  if (!sevSel || !statusSel || !tenantSel || !clearBtn) return;

  const active = Boolean(sevSel.value) || Boolean(statusSel.value) || Boolean(tenantSel.value);
  clearBtn.disabled = !active;
  sevSel.classList.toggle("filter-active", Boolean(sevSel.value));
  statusSel.classList.toggle("filter-active", Boolean(statusSel.value));
  tenantSel.classList.toggle("filter-active", Boolean(tenantSel.value));
}

function clearDLPFilters() {
  const sevSel = $("#dlp-severity-filter");
  const statusSel = $("#dlp-status-filter");
  const tenantSel = $("#dlp-tenant-filter");
  if (sevSel) sevSel.value = "";
  if (statusSel) statusSel.value = "";
  if (tenantSel) tenantSel.value = "";
  applyDLPFilters();
}

function renderIRMAlerts() {
  const alerts = currentData.irm?.alerts || [];
  const statusSel = $("#irm-status-filter");
  if (statusSel) {
    const cur = statusSel.value;
    const statuses = [...new Set(alerts.map(a => a.status).filter(Boolean))].sort();
    while (statusSel.options.length > 1) statusSel.remove(1);
    statuses.forEach(s => {
      const opt = document.createElement("option");
      opt.value = s;
      opt.textContent = s;
      statusSel.add(opt);
    });
    statusSel.value = cur;
  }
  applyIRMFilters();
}

function applyIRMFilters() {
  const alerts = currentData.irm?.alerts || [];
  const sevFilter = $("#irm-severity-filter")?.value || "";
  const statusFilter = $("#irm-status-filter")?.value || "";

  const filtered = alerts.filter(a => {
    if (sevFilter && (a.severity || "").toLowerCase() !== sevFilter) return false;
    if (statusFilter && a.status !== statusFilter) return false;
    return true;
  });

  const tbody = $("#irm-table tbody");
  if (filtered.length === 0) {
    const msg = alerts.length === 0 ? "No insider risk alerts" : "No alerts match the selected filters";
    tbody.innerHTML = `<tr><td colspan="6" class="placeholder-text">${msg}</td></tr>`;
  } else {
    tbody.innerHTML = filtered.map(a => `
      <tr>
        <td>${esc(a.title)}</td>
        <td>${severityBadge(a.severity)}</td>
        <td>${statusBadge(a.status)}</td>
        <td>${esc(a.policy_name)}</td>
        <td>${esc(a.created?.slice(0, 10) || "")}</td>
        <td>${esc(a.tenant_name)}</td>
      </tr>
    `).join("");
  }

  const sevSel = $("#irm-severity-filter");
  const stSel = $("#irm-status-filter");
  const clearBtn = $("#irm-clear-filters");
  if (sevSel && stSel && clearBtn) {
    const active = Boolean(sevSel.value) || Boolean(stSel.value);
    clearBtn.disabled = !active;
    sevSel.classList.toggle("filter-active", Boolean(sevSel.value));
    stSel.classList.toggle("filter-active", Boolean(stSel.value));
  }
}

function clearIRMFilters() {
  const sevSel = $("#irm-severity-filter");
  const stSel = $("#irm-status-filter");
  if (sevSel) sevSel.value = "";
  if (stSel) stSel.value = "";
  applyIRMFilters();
}

function renderSubjectRights() {
  const requests = currentData.subjectRights?.requests || [];
  const tbody = $("#srr-table tbody");
  if (requests.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="placeholder-text">No subject rights requests</td></tr>';
    return;
  }
  tbody.innerHTML = requests.map(r => `
    <tr>
      <td>${esc(r.display_name)}</td>
      <td>${esc(r.request_type)}</td>
      <td>${statusBadge(r.status)}</td>
      <td>${esc(r.created?.slice(0, 10) || "")}</td>
      <td>${esc(r.tenant_name)}</td>
    </tr>
  `).join("");
}

function renderCommCompliance() {
  const policies = currentData.commCompliance?.policies || [];
  const tbody = $("#comm-compliance-table tbody");
  if (policies.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="placeholder-text">No communication compliance policies</td></tr>';
    return;
  }
  tbody.innerHTML = policies.map(p => `
    <tr>
      <td>${esc(p.display_name)}</td>
      <td>${esc(p.policy_type)}</td>
      <td>${statusBadge(p.status)}</td>
      <td>${p.review_pending_count || 0}</td>
      <td>${esc(p.tenant_name)}</td>
    </tr>
  `).join("");
}

function renderInfoBarriers() {
  const policies = currentData.infoBarriers?.policies || [];
  const tbody = $("#info-barriers-table tbody");
  if (policies.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No information barrier policies</td></tr>';
    return;
  }
  tbody.innerHTML = policies.map(p => `
    <tr>
      <td>${esc(p.display_name)}</td>
      <td>${statusBadge(p.state)}</td>
      <td>${esc(p.segments_applied)}</td>
      <td>${esc(p.tenant_name)}</td>
    </tr>
  `).join("");
}

function renderAuditRecords() {
  const records = currentData.audit?.records || [];
  const tbody = $("#audit-table tbody");
  if (records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="placeholder-text">No audit records</td></tr>';
    return;
  }
  tbody.innerHTML = records.slice(0, 100).map(r => `
    <tr>
      <td>${esc(r.operation)}</td>
      <td>${esc(r.service)}</td>
      <td>${esc(r.user_id)}</td>
      <td>${esc(r.created?.slice(0, 16)?.replace("T", " ") || "")}</td>
    </tr>
  `).join("");
}

function renderGovernance() {
  const scopes = currentData.governance?.scopes || [];
  const tbody = $("#governance-table tbody");
  if (scopes.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="placeholder-text">No protection scopes</td></tr>';
    return;
  }
  tbody.innerHTML = scopes.map(s => `
    <tr>
      <td>${esc(s.scope_type)}</td>
      <td>${esc(s.execution_mode)}</td>
      <td>${esc(s.locations)}</td>
    </tr>
  `).join("");
}

// ── Improvement Actions ─────────────────────────────────────────────────────

function renderImprovementActions() {
  const data = currentData.actions || {};
  const score = data.secure_score || {};
  const scoreEl = $("#secure-score-value");
  if (scoreEl) {
    const cur = score.current_score ?? 0;
    const max = score.max_score ?? 0;
    scoreEl.textContent = max > 0 ? `${Math.round(cur)} / ${Math.round(max)}` : "–";
  }

  const actions = data.actions || [];
  populateActionsFilters(actions);
  applyActionsFilters();
}

function populateActionsFilters(actions) {
  const catSel = $("#actions-category-filter");
  if (!catSel) return;
  const cur = catSel.value;
  const categories = [...new Set(actions.map(a => a.control_category).filter(Boolean))].sort();
  while (catSel.options.length > 1) catSel.remove(1);
  categories.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    catSel.add(opt);
  });
  catSel.value = cur;
}

function applyActionsFilters() {
  const actions = currentData.actions?.actions || [];
  const catFilter = $("#actions-category-filter")?.value || "";
  const costFilter = $("#actions-cost-filter")?.value || "";
  const tierFilter = $("#actions-tier-filter")?.value || "";

  const filtered = actions.filter(a => {
    if (catFilter && a.control_category !== catFilter) return false;
    if (costFilter && a.implementation_cost !== costFilter) return false;
    if (tierFilter && a.tier !== tierFilter) return false;
    return true;
  });

  const tbody = $("#actions-table tbody");
  if (filtered.length === 0) {
    const msg = actions.length === 0 ? "No improvement actions" : "No actions match the selected filters";
    tbody.innerHTML = `<tr><td colspan="7" class="placeholder-text">${msg}</td></tr>`;
  } else {
    tbody.innerHTML = filtered.map(a => `
      <tr>
        <td>${a.rank || "–"}</td>
        <td title="${esc(a.remediation || "")}">${esc(a.title)}</td>
        <td>${esc(a.control_category)}</td>
        <td>${a.max_score || 0}</td>
        <td>${costBadge(a.implementation_cost)}</td>
        <td>${esc(a.tier)}</td>
        <td>${esc(a.service)}</td>
      </tr>
    `).join("");
  }

  updateActionsFilterState();
}

function costBadge(cost) {
  const c = (cost || "").toLowerCase();
  let cls = "badge--blue";
  if (c === "low") cls = "badge--green";
  else if (c === "moderate") cls = "badge--yellow";
  else if (c === "high") cls = "badge--red";
  return `<span class="badge ${cls}">${esc(cost)}</span>`;
}

function updateActionsFilterState() {
  const catSel = $("#actions-category-filter");
  const costSel = $("#actions-cost-filter");
  const tierSel = $("#actions-tier-filter");
  const clearBtn = $("#actions-clear-filters");
  if (!catSel || !costSel || !tierSel || !clearBtn) return;
  const active = Boolean(catSel.value) || Boolean(costSel.value) || Boolean(tierSel.value);
  clearBtn.disabled = !active;
  catSel.classList.toggle("filter-active", Boolean(catSel.value));
  costSel.classList.toggle("filter-active", Boolean(costSel.value));
  tierSel.classList.toggle("filter-active", Boolean(tierSel.value));
}

function clearActionsFilters() {
  const catSel = $("#actions-category-filter");
  const costSel = $("#actions-cost-filter");
  const tierSel = $("#actions-tier-filter");
  if (catSel) catSel.value = "";
  if (costSel) costSel.value = "";
  if (tierSel) tierSel.value = "";
  applyActionsFilters();
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
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
  if (s === "resolved" || s === "closed" || s === "active") cls = s === "active" ? "badge--green" : "badge--blue";
  if (s === "new" || s === "failed") cls = "badge--red";
  if (s === "inprogress" || s === "pending") cls = "badge--yellow";
  return `<span class="badge ${cls}">${esc(status)}</span>`;
}

function populateDepartments() {
  const tenants = currentData.overview?.tenants || [];
  const depts = [...new Set(tenants.map(t => t.department).filter(Boolean))];
  const sel = $("#department-filter");
  if (!sel) return;
  const current = sel.value;
  while (sel.options.length > 1) sel.remove(1);
  depts.sort().forEach(d => {
    const opt = document.createElement("option");
    opt.value = d;
    opt.textContent = d;
    sel.add(opt);
  });
  sel.value = current;
  updateFilterStateUI();
}

function getCurrentFilters() {
  const dept = $("#department-filter")?.value || "";
  const days = parseInt($("#days-filter")?.value || String(DEFAULT_DAYS), 10);
  return { dept, days: Number.isNaN(days) ? DEFAULT_DAYS : days };
}

function hasActiveFilters() {
  const { dept, days } = getCurrentFilters();
  return Boolean(dept) || days !== DEFAULT_DAYS;
}

function updateFilterStateUI() {
  const deptSelect = $("#department-filter");
  const daysSelect = $("#days-filter");
  const clearBtn = $("#clear-filters-btn");
  const summary = $("#filter-state-summary");
  if (!deptSelect || !daysSelect || !clearBtn || !summary) return;

  const { dept, days } = getCurrentFilters();
  const departmentLabel = dept || "All Departments";
  summary.textContent = `${departmentLabel} • ${days} days`;

  const active = hasActiveFilters();
  clearBtn.disabled = !active;
  deptSelect.classList.toggle("filter-active", Boolean(dept));
  daysSelect.classList.toggle("filter-active", days !== DEFAULT_DAYS);
}

function clearFilters() {
  const deptSelect = $("#department-filter");
  const daysSelect = $("#days-filter");
  if (!deptSelect || !daysSelect) return;
  deptSelect.value = "";
  daysSelect.value = String(DEFAULT_DAYS);
  updateFilterStateUI();
  loadData();
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
      content.innerHTML = `<p class="placeholder-text" style="color:var(--bad)">Error: ${esc(err.message)}</p>`;
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
    resp.classList.add("visible");
    resp.innerHTML = '<p class="placeholder-text">Thinking...</p>';
    try {
      const dept = $("#department-filter")?.value || "";
      const body = { question };
      if (dept) body.department = dept;
      const data = await api("ask", body);
      resp.innerHTML = `<div class="briefing-text">${formatBriefing(data.answer)}</div>`;
    } catch (err) {
      resp.innerHTML = `<p style="color:var(--bad)">${esc(err.message)}</p>`;
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
  $("#department-filter")?.addEventListener("change", () => {
    updateFilterStateUI();
    loadData();
  });
  $("#days-filter")?.addEventListener("change", () => {
    updateFilterStateUI();
    loadData();
  });
  $("#clear-filters-btn")?.addEventListener("click", clearFilters);

  $("#dlp-severity-filter")?.addEventListener("change", applyDLPFilters);
  $("#dlp-status-filter")?.addEventListener("change", applyDLPFilters);
  $("#dlp-tenant-filter")?.addEventListener("change", applyDLPFilters);
  $("#dlp-clear-filters")?.addEventListener("click", clearDLPFilters);

  $("#irm-severity-filter")?.addEventListener("change", applyIRMFilters);
  $("#irm-status-filter")?.addEventListener("change", applyIRMFilters);
  $("#irm-clear-filters")?.addEventListener("click", clearIRMFilters);

  $("#actions-category-filter")?.addEventListener("change", applyActionsFilters);
  $("#actions-cost-filter")?.addEventListener("change", applyActionsFilters);
  $("#actions-tier-filter")?.addEventListener("change", applyActionsFilters);
  $("#actions-clear-filters")?.addEventListener("click", clearActionsFilters);

  initSortableTables();
  initBriefing();
  initAdvisor();
  updateFilterStateUI();
  loadData();
});
