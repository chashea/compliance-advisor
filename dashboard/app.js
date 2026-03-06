/* ═══════════════════════════════════════════════════════════════════════════
   Compliance Advisor Dashboard — Compliance Manager Focus
   Fetches Compliance Score, Assessments, and Control data from the HTTP API.
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
let sortState = {}; // { tableId: { key, dir: 1|-1 } }

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
// DEMO DATA — aligned with Microsoft Purview Compliance Manager
// (implementation_status, test_status, categories per Purview docs)
// ═════════════════════════════════════════════════════════════════════════════

// Purview implementation status: notImplemented | planned | alternative | implemented | outOfScope
// Purview test status: notAssessed | none | inProgress | partiallyTested | passed | failed* | outOfScope
// Purview improvement action categories: Control Access, Discover and Respond, etc.
const PURVIEW_CATEGORIES = [
  "Control Access", "Discover and Respond", "Govern Information", "Infrastructure Cloud",
  "Manage Compliance", "Manage Devices", "Protect Against Threats", "Protect Information",
];

function generateDemoData(days) {
  const deptNames = ["Finance", "Health & Human Services", "Defense", "Education", "Energy"];
  const regulations = ["NIST 800-53 Rev 5", "ISO 27001:2022", "SOC 2 Type II", "CMMC Level 2", "FedRAMP Moderate"];
  const controlFamilies = [
    "Access Control", "Audit & Accountability", "Configuration Management",
    "Incident Response", "Risk Assessment", "System & Communications Protection",
    "Personnel Security", "Media Protection",
  ];

  const today = new Date();

  // Compliance score trend
  const complianceTrend = [];
  let base = 58;
  for (let i = days; i >= 0; i -= Math.max(1, Math.floor(days / 20))) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    base += (Math.random() - 0.35) * 1.2;
    base = Math.min(92, Math.max(35, base));
    complianceTrend.push({
      snapshot_date: d.toISOString().slice(0, 10),
      avg_compliance_pct: +base.toFixed(1),
      min_compliance_pct: +(base - 10 - Math.random() * 5).toFixed(1),
      max_compliance_pct: +(base + 6 + Math.random() * 7).toFixed(1),
    });
  }

  // Tenants
  const tenants = [
    "Contoso Corp", "Northwind Health", "Fabrikam Defense",
    "Woodgrove Education", "Litware Energy", "Adventure Works",
    "Fourth Coffee", "Tailspin Toys", "Trey Research",
  ];

  // Latest compliance scores per tenant
  const latestScores = tenants.map((name, i) => ({
    tenant_id: `tenant-${i}`,
    display_name: name,
    department: deptNames[i % deptNames.length],
    risk_tier: ["Critical", "High", "Medium", "Low"][i % 4],
    compliance_pct: +(45 + Math.random() * 45).toFixed(1),
    current_score: +(100 + Math.random() * 200).toFixed(0),
    max_score: 350,
    snapshot_date: today.toISOString().slice(0, 10),
  }));

  // Department rollup
  const deptRollup = deptNames.map((dept) => {
    const deptTenants = latestScores.filter((t) => t.department === dept);
    const avg = deptTenants.length
      ? deptTenants.reduce((s, t) => s + t.compliance_pct, 0) / deptTenants.length
      : 0;
    return {
      department: dept,
      tenant_count: deptTenants.length,
      avg_compliance_pct: +avg.toFixed(1),
      min_compliance_pct: +(avg - 8).toFixed(1),
      max_compliance_pct: +(avg + 12).toFixed(1),
      total_assessments: 2 + Math.floor(Math.random() * 4),
      total_failed_controls: Math.floor(Math.random() * 20),
    };
  });

  // Weekly changes
  const weeklyChanges = tenants.map((name, i) => {
    const current = latestScores[i].compliance_pct;
    const wow = +((Math.random() - 0.4) * 6).toFixed(1);
    return {
      display_name: name,
      department: deptNames[i % deptNames.length],
      current_pct: current,
      prior_pct: +(current - wow).toFixed(1),
      wow_change: wow,
      trend_direction: wow > 0.5 ? "Improving" : wow < -0.5 ? "Declining" : "Stable",
    };
  });

  // Assessments
  const assessments = [];
  tenants.forEach((name, i) => {
    const numAssess = 2 + Math.floor(Math.random() * 3);
    for (let j = 0; j < numAssess; j++) {
      const reg = regulations[j % regulations.length];
      const total = 40 + Math.floor(Math.random() * 60);
      const passed = Math.floor(total * (0.4 + Math.random() * 0.5));
      const failed = total - passed;
      assessments.push({
        tenant_id: `tenant-${i}`,
        display_name: name,
        department: deptNames[i % deptNames.length],
        assessment_name: `${reg} Assessment`,
        regulation: reg,
        status: "active",
        compliance_score: +((passed / total) * 100).toFixed(1),
        pass_rate: +((passed / total) * 100).toFixed(1),
        passed_controls: passed,
        failed_controls: failed,
        total_controls: total,
        last_modified: new Date(today - Math.random() * 7 * 86400000).toISOString().slice(0, 10),
      });
    }
  });

  // Regulation coverage
  const regulationCoverage = regulations.map((reg) => {
    const regAssess = assessments.filter((a) => a.regulation === reg);
    const totalPassed = regAssess.reduce((s, a) => s + a.passed_controls, 0);
    const totalAll = regAssess.reduce((s, a) => s + a.total_controls, 0);
    return {
      regulation: reg,
      tenant_count: new Set(regAssess.map((a) => a.tenant_id)).size,
      assessment_count: regAssess.length,
      avg_compliance_score: +(regAssess.reduce((s, a) => s + a.compliance_score, 0) / (regAssess.length || 1)).toFixed(1),
      total_passed: totalPassed,
      total_failed: totalAll - totalPassed,
      total_controls: totalAll,
      overall_pass_rate: +((totalPassed / (totalAll || 1)) * 100).toFixed(1),
    };
  });

  // Control family gaps
  const controlFamilyData = controlFamilies.map((fam) => {
    const total = 15 + Math.floor(Math.random() * 30);
    const implemented = Math.floor(total * (0.3 + Math.random() * 0.5));
    const passed = Math.floor(implemented * (0.6 + Math.random() * 0.3));
    const failed = implemented - passed;
    return {
      control_family: fam,
      total_controls: total,
      implemented,
      passed,
      failed,
      avg_gap: +((total - implemented) * 0.8 + Math.random() * 2).toFixed(1),
    };
  });

  // Top gaps — improvement actions with Purview-aligned implementation_status & test_status
  const topGaps = [
    { control_name: "AC-2 Account Management", control_family: "Access Control", control_category: "Control Access", regulation: "NIST 800-53 Rev 5", implementation_status: "notImplemented", test_status: "notAssessed", points_gap: 8.5, score_impact: "high", owner: "Identity Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Enable Azure AD Privileged Identity Management (PIM) for all admin roles.\n2. Configure access reviews on a 90-day cycle for all privileged accounts.\n3. Implement automated account provisioning/deprovisioning via SCIM.\n4. Deploy Conditional Access policies requiring MFA for all admin sign-ins.", test_plan: "Verify PIM activation logs exist for the past 30 days. Confirm access reviews completed with documented approvals. Run automated scan for orphaned accounts.", service: "Azure AD" },
    { control_name: "AU-6 Audit Review & Analysis", control_family: "Audit & Accountability", control_category: "Discover and Respond", regulation: "NIST 800-53 Rev 5", implementation_status: "planned", test_status: "notAssessed", points_gap: 7.2, score_impact: "high", owner: "SOC Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Enable Unified Audit Log in Microsoft 365.\n2. Configure Microsoft Sentinel with M365 data connector.\n3. Create analytics rules for anomalous sign-in patterns, data exfiltration, and privilege escalation.\n4. Establish weekly audit log review process with SOC rotation.", test_plan: "Confirm audit logs are flowing to Sentinel workspace. Verify at least 3 analytics rules are active. Review incident queue for past 7 days.", service: "Microsoft Sentinel" },
    { control_name: "CM-7 Least Functionality", control_family: "Configuration Management", control_category: "Manage Devices", regulation: "NIST 800-53 Rev 5", implementation_status: "notImplemented", test_status: "failedHighRisk", points_gap: 6.8, score_impact: "high", owner: "Endpoint Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Deploy Microsoft Defender for Endpoint attack surface reduction (ASR) rules.\n2. Disable unnecessary Windows services and features via Intune configuration profiles.\n3. Block execution of unsigned scripts using AppLocker / WDAC policies.\n4. Remove local admin rights from standard users using LAPS.", test_plan: "Run ASR rule audit report — confirm at least 10 rules in enforce mode. Scan 10 sample endpoints for disabled services. Verify AppLocker event logs show no bypasses.", service: "Intune" },
    { control_name: "A.8.1 Asset Management", control_family: "Asset Management", control_category: "Govern Information", regulation: "ISO 27001:2022", implementation_status: "alternative", test_status: "partiallyTested", points_gap: 5.9, score_impact: "medium", owner: "IT Operations", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Deploy Microsoft Defender for Endpoint device inventory across all managed devices.\n2. Configure automatic device tagging by department and sensitivity level.\n3. Integrate with Intune for software inventory and compliance checks.\n4. Establish quarterly asset reconciliation process.", test_plan: "Export device inventory — confirm 95% coverage vs HR headcount. Verify sensitivity labels applied to at least 80% of devices.", service: "Defender for Endpoint" },
    { control_name: "CC6.1 Logical Access Security", control_family: "Logical Access", control_category: "Control Access", regulation: "SOC 2 Type II", implementation_status: "planned", test_status: "toBeDetermined", points_gap: 5.4, score_impact: "medium", owner: "Identity Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Enforce MFA for all users via Conditional Access (Security Defaults minimum).\n2. Implement risk-based Conditional Access requiring step-up for high-risk sign-ins.\n3. Configure session controls to limit persistent browser sessions to 12 hours.\n4. Deploy passwordless authentication (FIDO2 / Windows Hello) for privileged users.", test_plan: "Pull sign-in logs confirming MFA challenge rate > 99%. Validate CA policies cover all cloud apps. Test passwordless flow for 5 admin accounts.", service: "Azure AD" },
    { control_name: "IR-4 Incident Handling", control_family: "Incident Response", control_category: "Discover and Respond", regulation: "NIST 800-53 Rev 5", implementation_status: "notImplemented", test_status: "failedMediumRisk", points_gap: 4.8, score_impact: "medium", owner: "SOC Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Create incident response playbooks in Microsoft Sentinel (Logic App automation).\n2. Configure automated incident enrichment with threat intelligence.\n3. Set up automated notification to CISO for Severity 1 incidents.\n4. Schedule quarterly tabletop exercises and document lessons learned.", test_plan: "Trigger test incident and verify playbook executes within 5 minutes. Confirm enrichment adds TI context. Verify notification reaches CISO inbox.", service: "Microsoft Sentinel" },
    { control_name: "SC-8 Transmission Confidentiality", control_family: "System & Communications Protection", control_category: "Protect Information", regulation: "FedRAMP Moderate", implementation_status: "planned", test_status: "inProgress", points_gap: 4.3, score_impact: "low", owner: "Network Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Enforce TLS 1.2+ across all M365 services and disable legacy protocols.\n2. Configure Exchange Online to require TLS for partner domain connectors.\n3. Enable Microsoft Purview Information Protection for sensitive data in transit.\n4. Deploy Azure Private Link for internal traffic to PaaS services.", test_plan: "Run TLS configuration scan across all endpoints. Verify no TLS 1.0/1.1 connections in past 30 days. Confirm sensitivity labels applied to email containing PII.", service: "Exchange Online" },
    { control_name: "RA-5 Vulnerability Scanning", control_family: "Risk Assessment", control_category: "Protect Against Threats", regulation: "CMMC Level 2", implementation_status: "notImplemented", test_status: "failedLowRisk", points_gap: 3.9, score_impact: "low", owner: "SecOps Team", action_url: "https://compliance.microsoft.com/compliancemanager", implementation_details: "1. Enable Microsoft Defender Vulnerability Management across all enrolled devices.\n2. Configure weekly automated vulnerability scans.\n3. Establish SLA for remediation: Critical 48h, High 7d, Medium 30d, Low 90d.\n4. Create Power BI dashboard for vulnerability trending and SLA compliance.", test_plan: "Confirm scan coverage ≥ 95% of managed devices. Pull vulnerability report showing remediation within SLA for past quarter. Verify Critical vulnerabilities at 0 for > 48h.", service: "Defender Vulnerability Mgmt" },
  ];

  return {
    status: {
      active_tenants: tenants.length,
      newest_sync: today.toISOString().slice(0, 10),
    },
    compliance: {
      latest_scores: latestScores,
      compliance_trend: complianceTrend,
      weekly_changes: weeklyChanges,
      department_rollup: deptRollup,
    },
    assessments: {
      assessments,
      top_gaps: topGaps,
      control_families: controlFamilyData,
    },
    regulations: {
      regulations: regulationCoverage,
    },
    actions: {
      actions: topGaps.map((g, i) => ({
        ...g,
        display_name: tenants[i % tenants.length],
        assessment_name: `${g.regulation} Assessment`,
        priority_rank: g.score_impact === "high" ? 1 : g.score_impact === "medium" ? 3 : 5,
      })),
      summary: {
        total_actions: topGaps.length,
        high_impact: topGaps.filter((g) => g.score_impact === "high").length,
        medium_impact: topGaps.filter((g) => g.score_impact === "medium").length,
        low_impact: topGaps.filter((g) => g.score_impact === "low").length,
        total_points_gap: +topGaps.reduce((s, g) => s + g.points_gap, 0).toFixed(1),
        distinct_owners: new Set(topGaps.map((g) => g.owner)).size,
        distinct_regulations: new Set(topGaps.map((g) => g.regulation)).size,
        distinct_services: new Set(topGaps.map((g) => g.service)).size,
      },
      owner_breakdown: [...new Set(topGaps.map((g) => g.owner))].map((owner) => {
        const ownActions = topGaps.filter((g) => g.owner === owner);
        return {
          owner,
          action_count: ownActions.length,
          total_gap: +ownActions.reduce((s, g) => s + g.points_gap, 0).toFixed(1),
          high_impact: ownActions.filter((g) => g.score_impact === "high").length,
        };
      }),
    },
  };
}

// ═════════════════════════════════════════════════════════════════════════════
// DATA LOADING
// ═════════════════════════════════════════════════════════════════════════════

async function loadDashboard() {
  const department = $("#department-filter").value;
  const days = parseInt($("#days-filter").value, 10);
  const forceDemo = $("#demo-mode-toggle")?.checked ?? false;

  setStatus("loading", "Loading compliance data…");
  setLoadingSkeleton(true);

  try {
    if (forceDemo) {
      demoMode = true;
      currentData = generateDemoData(days);
    } else {
      const [statusData, complianceData, assessmentData, regulationData, actionsData] = await Promise.all([
        api("status"),
        api("compliance", { department: department || undefined, days }),
        api("assessments", { department: department || undefined }),
        api("regulations"),
        api("actions", { department: department || undefined }),
      ]);

      currentData = {
        status: statusData,
        compliance: complianceData,
        assessments: assessmentData,
        regulations: regulationData,
        actions: actionsData,
      };
      demoMode = false;
    }
  } catch (err) {
    console.warn("API unavailable — loading demo data.", err.message);
    demoMode = true;
    currentData = generateDemoData(days);
  }

  setLoadingSkeleton(false);

  const { status: statusData, compliance, assessments: assessmentData, regulations: regulationData, actions: actionsData } = currentData;

  // Populate department filter
  populateDepartmentFilter(compliance.department_rollup);

  // Render everything
  renderKPIs(compliance, assessmentData, statusData);
  renderTrendChart(compliance.compliance_trend);
  renderDepartmentChart(compliance.department_rollup);
  renderRegulationChart(regulationData.regulations);
  renderFamilyChart(assessmentData.control_families);
  renderAssessmentTable(assessmentData.assessments, { sorted: getSorted("assessment-table", assessmentData.assessments, assessmentTableSortKeys) });
  renderWoWTable(compliance.weekly_changes, { sorted: getSorted("wow-table", compliance.weekly_changes, wowTableSortKeys) });
  renderGapsTable(assessmentData.top_gaps);
  renderActionsTable(actionsData);
  renderActionsSummary(actionsData?.summary);

  updateSortHeaders("assessment-table");
  updateSortHeaders("wow-table");

  // Enable Copy when briefing has real content
  const briefingEl = $("#briefing-content");
  const copyBtn = $("#copy-briefing-btn");
  if (copyBtn) copyBtn.disabled = !briefingEl?.innerText?.trim() || briefingEl.innerText.includes("Click \"Generate Briefing\"");

  if (demoMode) {
    setStatus("ok", "DEMO MODE — showing sample Compliance Manager data (API unavailable)");
  } else {
    setStatus("ok",
      `Last sync: ${statusData.newest_sync || "never"} · ${statusData.active_tenants} tenant(s)`
    );
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// KPI RENDERING
// ═════════════════════════════════════════════════════════════════════════════

function renderKPIs(compliance, assessmentData, status) {
  const changes = compliance.weekly_changes || [];
  const trend = compliance.compliance_trend || [];
  const assessments = assessmentData?.assessments || [];

  // Average compliance score from latest trend data point
  let avgPct = "–";
  if (trend.length > 0) {
    const latest = trend[trend.length - 1];
    avgPct = latest.avg_compliance_pct ?? "–";
  } else if (compliance.latest_scores?.length) {
    const scores = compliance.latest_scores;
    avgPct = (scores.reduce((s, t) => s + (t.compliance_pct || 0), 0) / scores.length).toFixed(1);
  }

  const improving = changes.filter((c) => c.trend_direction === "Improving").length;
  const declining = changes.filter((c) => c.trend_direction === "Declining").length;
  const totalFailed = assessments.reduce((s, a) => s + (a.failed_controls || 0), 0);

  $("#kpi-avg").textContent = avgPct !== "–" ? `${avgPct}%` : "–";
  $("#kpi-tenants").textContent = status.active_tenants ?? "–";
  $("#kpi-assessments").textContent = assessments.length || "–";
  $("#kpi-improving").textContent = improving;
  $("#kpi-declining").textContent = declining;
  $("#kpi-failed").textContent = totalFailed || "–";
}

// ═════════════════════════════════════════════════════════════════════════════
// DEPARTMENT FILTER
// ═════════════════════════════════════════════════════════════════════════════

let deptFilterPopulated = false;
function populateDepartmentFilter(departments) {
  if (deptFilterPopulated || !departments?.length) return;
  const sel = $("#department-filter");
  const current = sel.value;
  departments.forEach((d) => {
    if (!d.department) return;
    const opt = document.createElement("option");
    opt.value = d.department;
    opt.textContent = d.department;
    sel.appendChild(opt);
  });
  sel.value = current;
  deptFilterPopulated = true;
}

// ═════════════════════════════════════════════════════════════════════════════
// CHARTS
// ═════════════════════════════════════════════════════════════════════════════

function destroyChart(key) {
  if (charts[key]) { charts[key].destroy(); delete charts[key]; }
}

function renderEmpty(ctx, message) {
  return new Chart(ctx, {
    type: "bar",
    data: { labels: [message], datasets: [{ data: [0] }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { display: false }, y: { display: false } },
    },
  });
}

// Compliance Score Trend (line chart)
function renderTrendChart(data) {
  destroyChart("trend");
  const ctx = $("#trend-chart").getContext("2d");

  if (!data?.length) { charts.trend = renderEmpty(ctx, "No compliance trend data"); return; }

  const labels = data.map((d) => d.snapshot_date);
  const datasets = [];

  if (data[0].avg_compliance_pct != null) {
    datasets.push(
      { label: "Average", data: data.map((d) => d.avg_compliance_pct), borderColor: CHART_COLORS.blue, backgroundColor: "rgba(79,143,247,.1)", fill: true, tension: 0.3 },
      { label: "Min", data: data.map((d) => d.min_compliance_pct), borderColor: CHART_COLORS.red, borderDash: [4, 4], tension: 0.3, pointRadius: 0 },
      { label: "Max", data: data.map((d) => d.max_compliance_pct), borderColor: CHART_COLORS.green, borderDash: [4, 4], tension: 0.3, pointRadius: 0 },
    );
  } else {
    datasets.push(
      { label: "Compliance %", data: data.map((d) => d.compliance_pct), borderColor: CHART_COLORS.blue, backgroundColor: "rgba(79,143,247,.1)", fill: true, tension: 0.3 },
    );
  }

  charts.trend = new Chart(ctx, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
      scales: {
        y: { beginAtZero: false, title: { display: true, text: "Compliance %" } },
        x: { ticks: { maxTicksLimit: 10, maxRotation: 0 } },
      },
    },
  });
}

// Department Compliance (horizontal bar)
function renderDepartmentChart(data) {
  destroyChart("dept");
  const ctx = $("#dept-chart").getContext("2d");

  if (!data?.length) { charts.dept = renderEmpty(ctx, "No department data"); return; }

  const sorted = [...data].sort((a, b) =>
    (a.avg_compliance_pct ?? a.avg_score_pct ?? 0) - (b.avg_compliance_pct ?? b.avg_score_pct ?? 0)
  );

  charts.dept = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.department),
      datasets: [{
        label: "Avg Compliance %",
        data: sorted.map((d) => d.avg_compliance_pct ?? d.avg_score_pct),
        backgroundColor: sorted.map((d) => {
          const v = d.avg_compliance_pct ?? d.avg_score_pct ?? 0;
          return v < 50 ? CHART_COLORS.red : v < 70 ? CHART_COLORS.yellow : CHART_COLORS.green;
        }),
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: "y",
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, max: 100, title: { display: true, text: "Compliance %" } } },
      onClick: (_ev, elements) => {
        if (elements.length && $("#department-filter")) {
          const idx = elements[0].index;
          const dept = sorted[idx]?.department;
          if (dept) {
            $("#department-filter").value = dept;
            loadDashboard();
          }
        }
      },
    },
  });
}

// Regulation Coverage (horizontal bar — pass rate per regulation)
function renderRegulationChart(data) {
  destroyChart("regulation");
  const ctx = $("#regulation-chart").getContext("2d");

  if (!data?.length) { charts.regulation = renderEmpty(ctx, "No regulation data"); return; }

  const sorted = [...data].sort((a, b) => a.overall_pass_rate - b.overall_pass_rate);

  charts.regulation = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.regulation),
      datasets: [
        {
          label: "Pass Rate %",
          data: sorted.map((d) => d.overall_pass_rate),
          backgroundColor: sorted.map((d) =>
            d.overall_pass_rate < 50 ? CHART_COLORS.red :
            d.overall_pass_rate < 70 ? CHART_COLORS.yellow :
            CHART_COLORS.green
          ),
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { x: { beginAtZero: true, max: 100, title: { display: true, text: "Pass Rate %" } } },
    },
  });
}

// Control Family Gaps (grouped bar — implemented vs. total)
function renderFamilyChart(data) {
  destroyChart("family");
  const ctx = $("#family-chart").getContext("2d");

  if (!data?.length) { charts.family = renderEmpty(ctx, "No control family data"); return; }

  const sorted = [...data].sort((a, b) => b.avg_gap - a.avg_gap);

  charts.family = new Chart(ctx, {
    type: "bar",
    data: {
      labels: sorted.map((d) => d.control_family),
      datasets: [
        {
          label: "Implemented",
          data: sorted.map((d) => d.implemented),
          backgroundColor: CHART_COLORS.green,
          borderRadius: 4,
        },
        {
          label: "Not Implemented",
          data: sorted.map((d) => d.total_controls - d.implemented),
          backgroundColor: CHART_COLORS.red + "88",
          borderRadius: 4,
        },
        {
          label: "Failed Tests",
          data: sorted.map((d) => d.failed),
          backgroundColor: CHART_COLORS.orange,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "top", labels: { boxWidth: 12 } } },
      scales: {
        x: { stacked: false, ticks: { maxRotation: 45 } },
        y: { beginAtZero: true, title: { display: true, text: "Controls" } },
      },
    },
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// TABLES
// ═════════════════════════════════════════════════════════════════════════════

function renderAssessmentTable(assessments, options = {}) {
  const tbody = $("#assessment-table tbody");
  tbody.innerHTML = "";
  const list = options.sorted ?? assessments ?? [];

  if (!list?.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text-muted)">No assessment data</td></tr>';
    return;
  }

  list.forEach((a) => {
    const scoreCls = (a.compliance_score ?? a.pass_rate) < 50 ? "kpi-card__value--bad" :
                     (a.compliance_score ?? a.pass_rate) < 70 ? "" : "kpi-card__value--good";
    tbody.innerHTML += `
      <tr>
        <td>${esc(a.assessment_name)}</td>
        <td>${esc(a.regulation || "–")}</td>
        <td>${esc(a.display_name || "–")}</td>
        <td class="${scoreCls}">${a.compliance_score != null ? a.compliance_score + "%" : "–"}</td>
        <td>${a.pass_rate != null ? a.pass_rate + "%" : "–"}</td>
        <td style="color:var(--good)">${a.passed_controls ?? "–"}</td>
        <td style="color:var(--bad)">${a.failed_controls ?? "–"}</td>
        <td>${a.total_controls ?? "–"}</td>
      </tr>`;
  });
}

const assessmentTableSortKeys = ["assessment_name", "regulation", "display_name", "compliance_score", "pass_rate", "passed_controls", "failed_controls", "total_controls"];
const wowTableSortKeys = ["display_name", "department", "current_pct", "prior_pct", "wow_change", "trend_direction"];

function getSorted(tableId, data, keys) {
  if (!data?.length) return data;
  const state = sortState[tableId];
  if (!state?.key) return data;
  const key = state.key;
  const dir = state.dir || 1;
  const isNum = $(`#${tableId} thead th[data-sort="${key}"]`)?.hasAttribute("data-sort-num");
  return [...data].sort((a, b) => {
    let va = a[key];
    let vb = b[key];
    if (isNum) {
      va = Number(va);
      vb = Number(vb);
      return dir * (isNaN(va) ? 0 : va - (isNaN(vb) ? 0 : vb));
    }
    const sa = String(va ?? "").toLowerCase();
    const sb = String(vb ?? "").toLowerCase();
    return dir * (sa < sb ? -1 : sa > sb ? 1 : 0);
  });
}

function updateSortHeaders(tableId) {
  const table = $(`#${tableId}`);
  if (!table) return;
  const state = sortState[tableId];
  table.querySelectorAll("thead th[data-sort]").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    const icon = th.querySelector(".sort-icon");
    if (icon) icon.textContent = "";
    if (state?.key === th.getAttribute("data-sort")) {
      th.classList.add(state.dir === 1 ? "sorted-asc" : "sorted-desc");
      if (icon) icon.textContent = state.dir === 1 ? " ▲" : " ▼";
    }
  });
}

function reapplySortAndRenderTables() {
  const { compliance, assessments: assessmentData, actions: actionsData } = currentData;
  if (!compliance || !assessmentData) return;
  renderAssessmentTable(assessmentData.assessments, { sorted: getSorted("assessment-table", assessmentData.assessments, assessmentTableSortKeys) });
  renderWoWTable(compliance.weekly_changes, { sorted: getSorted("wow-table", compliance.weekly_changes, wowTableSortKeys) });
  updateSortHeaders("assessment-table");
  updateSortHeaders("wow-table");
}

function renderWoWTable(changes, options = {}) {
  const tbody = $("#wow-table tbody");
  tbody.innerHTML = "";
  const list = options.sorted ?? changes ?? [];

  if (!list?.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted)">No data</td></tr>';
    return;
  }

  list.forEach((c) => {
    const dir = c.trend_direction || "Stable";
    const cls = dir === "Improving" ? "badge--improving" :
                dir === "Declining" ? "badge--declining" : "badge--stable";
    const changeStr = c.wow_change != null
      ? `${c.wow_change > 0 ? "+" : ""}${c.wow_change.toFixed(1)}%` : "–";

    tbody.innerHTML += `
      <tr>
        <td>${esc(c.display_name)}</td>
        <td>${esc(c.department || "–")}</td>
        <td>${c.current_pct != null ? c.current_pct + "%" : "–"}</td>
        <td>${c.prior_pct != null ? c.prior_pct + "%" : "–"}</td>
        <td>${changeStr}</td>
        <td><span class="badge ${cls}">${dir}</span></td>
      </tr>`;
  });
}

function renderGapsTable(gaps) {
  const tbody = $("#gaps-table tbody");
  tbody.innerHTML = "";

  if (!gaps?.length) {
    tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text-muted)">No data</td></tr>';
    return;
  }

  gaps.forEach((g) => {
    const impl = g.implementation_status;
    const implClass = impl === "notImplemented" ? "badge--declining" : impl === "implemented" ? "badge--improving" : impl === "outOfScope" ? "badge--stable" : "badge--stable";
    const statusBadge = impl ? `<span class="badge ${implClass}">${esc(purviewImplementationLabel(impl))}</span>` : `<span class="badge">${esc(purviewTestLabel(g.test_status))}</span>`;

    const impactBadge = g.score_impact
      ? `<span class="badge badge--${g.score_impact}">${esc(g.score_impact)}</span>`
      : "–";

    const actionLink = g.action_url
      ? `<a href="${esc(g.action_url)}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.8rem">Open ↗</a>`
      : "–";

    tbody.innerHTML += `
      <tr>
        <td>${esc(g.control_name)}</td>
        <td>${esc(g.control_family || g.control_category || "–")}</td>
        <td>${statusBadge}</td>
        <td>${impactBadge}</td>
        <td>${g.points_gap != null ? g.points_gap.toFixed(1) : "–"}</td>
        <td>${esc(g.owner || "–")}</td>
        <td>${actionLink}</td>
      </tr>`;
  });
}

// Improvement Actions Summary Bar
function renderActionsSummary(summary) {
  const el = $("#actions-summary");
  if (!summary) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <span class="actions-summary__stat"><strong>${summary.total_actions || 0}</strong> Actions</span>
    <span class="actions-summary__stat"><span class="badge badge--high">${summary.high_impact || 0}</span> High Impact</span>
    <span class="actions-summary__stat"><span class="badge badge--medium">${summary.medium_impact || 0}</span> Medium</span>
    <span class="actions-summary__stat"><span class="badge badge--low">${summary.low_impact || 0}</span> Low</span>
    <span class="actions-summary__stat"><strong>${summary.total_points_gap ?? 0}</strong> Total Pts Gap</span>
    <span class="actions-summary__stat"><strong>${summary.distinct_owners || 0}</strong> Owners</span>
  `;
}

// Improvement Actions Table — expandable rows with solution details
function renderActionsTable(actionsData) {
  const tbody = $("#actions-table tbody");
  tbody.innerHTML = "";

  const actions = actionsData?.actions || [];
  if (!actions.length) {
    tbody.innerHTML = '<tr><td colspan="8" style="color:var(--text-muted)">No improvement actions data</td></tr>';
    return;
  }

  actions.forEach((a, idx) => {
    const impl = a.implementation_status;
    const implClass = impl === "notImplemented" ? "badge--declining" : impl === "implemented" ? "badge--improving" : impl === "outOfScope" ? "badge--stable" : "badge--stable";
    const statusBadge = impl ? `<span class="badge ${implClass}">${esc(purviewImplementationLabel(impl))}</span>` : `<span class="badge">–</span>`;

    const impactBadge = a.score_impact
      ? `<span class="badge badge--${a.score_impact}">${esc(a.score_impact)}</span>`
      : "–";

    // Main row
    tbody.innerHTML += `
      <tr data-action-idx="${idx}" class="action-main-row">
        <td><button class="expand-btn" aria-label="Expand details">▶</button></td>
        <td>${esc(a.control_name)}</td>
        <td>${esc(a.regulation || a.assessment_name || "–")}</td>
        <td>${statusBadge}</td>
        <td>${impactBadge}</td>
        <td>${a.points_gap != null ? a.points_gap.toFixed(1) : "–"}</td>
        <td>${esc(a.owner || "–")}</td>
        <td>${esc(a.service || "–")}</td>
      </tr>
      <tr class="action-detail-row" id="action-detail-${idx}" style="display:none">
        <td colspan="8">
          <div class="action-detail">
            <div class="action-detail__section">
              <h4>Implementation Steps</h4>
              <p class="${a.implementation_details ? "" : "empty"}">${esc(a.implementation_details || "No implementation details available.")}</p>
            </div>
            <div class="action-detail__section">
              <h4>Test Plan / Evidence Required</h4>
              <p class="${a.test_plan ? "" : "empty"}">${esc(a.test_plan || "No test plan documented.")}</p>
            </div>
            ${a.management_response ? `
            <div class="action-detail__section">
              <h4>Management Response</h4>
              <p>${esc(a.management_response)}</p>
            </div>` : ""}
            <div class="action-detail__section">
              <h4>Details</h4>
              <p><strong>Family:</strong> ${esc(a.control_family || "–")}<br>
                 <strong>Service:</strong> ${esc(a.service || "–")}<br>
                 <strong>Owner:</strong> ${esc(a.owner || "–")}<br>
                 <strong>Assessment:</strong> ${esc(a.assessment_name || "–")}</p>
              ${a.action_url ? `<a class="action-detail__link" href="${esc(a.action_url)}" target="_blank" rel="noopener">Open in Compliance Manager ↗</a>` : ""}
            </div>
          </div>
        </td>
      </tr>`;
  });

  attachActionExpandHandlers(tbody);
}

function attachActionExpandHandlers(tbody) {
  if (!tbody) return;
  tbody.querySelectorAll(".action-main-row").forEach((row) => {
    row.replaceWith(row.cloneNode(true));
  });
  tbody.querySelectorAll(".action-main-row").forEach((row) => {
    row.addEventListener("click", () => {
      const idx = row.dataset.actionIdx;
      const detail = document.getElementById(`action-detail-${idx}`);
      const btn = row.querySelector(".expand-btn");
      if (!detail || !btn) return;
      const visible = detail.style.display !== "none";
      detail.style.display = visible ? "none" : "table-row";
      btn.classList.toggle("open", !visible);
    });
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// EXECUTIVE BRIEFING
// ═════════════════════════════════════════════════════════════════════════════

async function generateBriefing() {
  const btn = $("#generate-briefing-btn");
  const content = $("#briefing-content");
  const department = $("#department-filter").value;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Generating…';
  content.innerHTML = '<span class="placeholder-text">Generating compliance briefing…</span>';

  try {
    if (demoMode) {
      await new Promise((r) => setTimeout(r, 800));
      content.innerHTML = buildDemoBriefing();
    } else {
      const result = await api("briefing", { department: department || undefined });
      content.innerHTML = result.briefing
        ? `<pre style="white-space:pre-wrap;font-family:inherit">${esc(result.briefing)}</pre>`
        : formatBriefingData(result);
    }
  } catch (err) {
    content.innerHTML = `<span style="color:var(--bad)">Error: ${esc(err.message)}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Briefing";
    const copyBtn = $("#copy-briefing-btn");
    if (copyBtn) copyBtn.disabled = !$("#briefing-content")?.innerText?.trim() || $("#briefing-content").innerText.includes("Click \"Generate Briefing\"");
  }
}

function formatBriefingData(data) {
  let html = "";
  if (data.scores?.length) {
    const avg = (data.scores.reduce((s, t) => s + (t.compliance_pct || t.score_pct || 0), 0) / data.scores.length).toFixed(1);
    html += `<strong>Enterprise Compliance Average:</strong> ${avg}%<br>`;
    html += `<strong>Tenants:</strong> ${data.scores.length}<br><br>`;
    html += "<strong>Per-Tenant Scores:</strong><br>";
    data.scores.forEach((s) => {
      html += `  • ${esc(s.display_name)} (${esc(s.department || "N/A")}): ${s.compliance_pct || s.score_pct}%<br>`;
    });
  }
  if (data.top_gaps?.length) {
    html += "<br><strong>Top Assessment Gaps:</strong><br>";
    data.top_gaps.forEach((g) => {
      html += `  • ${esc(g.control_name)} [${esc(g.control_family || g.regulation || "")}]: ${g.points_gap?.toFixed(1)} pt gap — ${g.implementation_status}<br>`;
    });
  }
  return html || '<span class="placeholder-text">No briefing data available.</span>';
}

// ═════════════════════════════════════════════════════════════════════════════
// ASK THE ADVISOR
// ═════════════════════════════════════════════════════════════════════════════

async function askAdvisor() {
  const input = $("#ask-input");
  const btn = $("#ask-btn");
  const resp = $("#ask-response");
  const question = input.value.trim();
  if (!question) return;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  resp.className = "ask-response visible";
  resp.textContent = "Thinking…";

  try {
    if (demoMode) {
      await new Promise((r) => setTimeout(r, 1200));
      resp.textContent = getDemoAnswer(question);
    } else {
      const result = await api("ask", { question, cross_tenant: true });
      resp.textContent = result.answer || "No response received.";
    }
  } catch (err) {
    resp.innerHTML = `<span style="color:var(--bad)">Error: ${esc(err.message)}</span>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Ask";
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// DEMO MODE HELPERS
// ═════════════════════════════════════════════════════════════════════════════

function buildDemoBriefing() {
  const d = currentData;
  const trend = d.compliance?.compliance_trend || [];
  const latest = trend.length ? trend[trend.length - 1] : {};
  const depts = d.compliance?.department_rollup || [];
  const topDept = [...depts].sort((a, b) => (b.avg_compliance_pct || 0) - (a.avg_compliance_pct || 0))[0];
  const botDept = [...depts].sort((a, b) => (a.avg_compliance_pct || 0) - (b.avg_compliance_pct || 0))[0];
  const changes = d.compliance?.weekly_changes || [];
  const improving = changes.filter((c) => c.trend_direction === "Improving").length;
  const declining = changes.filter((c) => c.trend_direction === "Declining").length;
  const assessments = d.assessments?.assessments || [];
  const regulations = d.regulations?.regulations || [];

  return `<strong>COMPLIANCE MANAGER EXECUTIVE BRIEFING</strong> — ${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}<br><br>`
    + `<strong>Enterprise Compliance Posture:</strong> The current enterprise-wide Compliance Score average is <strong>${latest.avg_compliance_pct ?? "–"}%</strong> `
    + `(range ${latest.min_compliance_pct ?? "–"}% – ${latest.max_compliance_pct ?? "–"}%). `
    + `${improving} tenant(s) improved this week while ${declining} declined.<br><br>`
    + `<strong>Assessment Coverage:</strong> ${assessments.length} active assessments across ${regulations.length} regulatory frameworks. `
    + `Frameworks tracked: ${regulations.map((r) => r.regulation).join(", ")}.<br><br>`
    + `<strong>Department Scorecard:</strong> ${topDept ? `${topDept.department} leads at ${topDept.avg_compliance_pct}%.` : ""} `
    + `${botDept ? `${botDept.department} trails at ${botDept.avg_compliance_pct}% and requires focused remediation.` : ""}<br><br>`
    + `<strong>Top Compliance Gaps Requiring Action:</strong><br>`
    + (d.assessments?.top_gaps || []).slice(0, 5).map((g, i) =>
        `  ${i + 1}. ${g.control_name} (${g.control_family}) — ${g.points_gap} pt gap [${g.implementation_status}]`
      ).join("<br>")
    + `<br><br><em>This is a demo briefing generated from sample Compliance Manager data.</em>`;
}

function getDemoAnswer(question) {
  const q = question.toLowerCase();
  if (q.includes("nist") || q.includes("800-53")) {
    return "NIST 800-53 Rev 5 Assessment Status:\n\n"
      + "• Enterprise-wide pass rate: ~62%\n"
      + "• Top gaps by control family:\n"
      + "  1. AC-2 Account Management — 8.5 pt gap (Not Implemented)\n"
      + "  2. AU-6 Audit Review & Analysis — 7.2 pt gap (Planned)\n"
      + "  3. CM-7 Least Functionality — 6.8 pt gap (Not Implemented)\n"
      + "  4. IR-4 Incident Handling — 4.8 pt gap (Not Implemented)\n\n"
      + "Priority: Implement AC-2 and CM-7 controls across all tenants for the largest compliance score improvement.\n\n"
      + "[Demo mode — connect to the API for live AI-powered responses]";
  }
  if (q.includes("assessment") || q.includes("regulation") || q.includes("framework")) {
    return "Active Assessment Summary:\n\n"
      + "• NIST 800-53 Rev 5 — 9 tenants, ~62% avg pass rate\n"
      + "• ISO 27001:2022 — 9 tenants, ~68% avg pass rate\n"
      + "• SOC 2 Type II — 9 tenants, ~65% avg pass rate\n"
      + "• CMMC Level 2 — 9 tenants, ~59% avg pass rate\n"
      + "• FedRAMP Moderate — 9 tenants, ~61% avg pass rate\n\n"
      + "CMMC Level 2 has the lowest pass rate and should be prioritized for remediation.\n\n"
      + "[Demo mode — connect to the API for live AI-powered responses]";
  }
  if (q.includes("gap") || q.includes("control") || q.includes("fail")) {
    return "Top Compliance Control Gaps:\n\n"
      + "1. AC-2 Account Management (Access Control) — 8.5 pt gap\n"
      + "2. AU-6 Audit Review & Analysis (Audit & Accountability) — 7.2 pt gap\n"
      + "3. CM-7 Least Functionality (Configuration Management) — 6.8 pt gap\n"
      + "4. A.8.1 Asset Management (ISO 27001) — 5.9 pt gap\n"
      + "5. CC6.1 Logical Access Security (SOC 2) — 5.4 pt gap\n\n"
      + "These gaps span Access Control and Audit families. Implementing centralized identity governance would address the top 2.\n\n"
      + "[Demo mode — connect to the API for live AI-powered responses]";
  }
  if (q.includes("department") || q.includes("agency")) {
    return "Department Compliance Breakdown:\n\n"
      + "• Finance — 74% avg compliance (3 tenants, improving)\n"
      + "• Education — 69% avg compliance (2 tenants, stable)\n"
      + "• Energy — 62% avg compliance (2 tenants, improving)\n"
      + "• Health & Human Services — 55% avg compliance (3 tenants, mixed)\n"
      + "• Defense — 48% avg compliance (2 tenants, declining)\n\n"
      + "Defense requires immediate attention — CMMC Level 2 assessment is at 38% pass rate.\n\n"
      + "[Demo mode — connect to the API for live AI-powered responses]";
  }
  if (q.includes("score") || q.includes("lowest") || q.includes("worst")) {
    return "Enterprise Compliance Score is approximately 62%.\n\n"
      + "Lowest-scoring tenants:\n"
      + "• Fabrikam Defense — 45% (Defense dept, Critical risk tier)\n"
      + "• Tailspin Toys — 48% (Education dept, Medium risk tier)\n\n"
      + "Primary gaps are in Access Control and Audit & Accountability control families.\n\n"
      + "[Demo mode — connect to the API for live AI-powered responses]";
  }
  return "Enterprise Compliance Manager Summary:\n\n"
    + "• 9 tenants monitored across 5 departments\n"
    + "• 5 regulatory frameworks assessed (NIST, ISO, SOC 2, CMMC, FedRAMP)\n"
    + "• Average compliance score: ~62%\n"
    + "• 6 tenants improved this week\n\n"
    + "Try asking about specific topics: 'NIST 800-53 status', 'top gaps', 'department compliance', or 'assessment coverage'.\n\n"
    + "[Demo mode — connect to the API for live AI-powered responses]";
}

// ═════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═════════════════════════════════════════════════════════════════════════════

function esc(str) {
  const el = document.createElement("span");
  el.textContent = str ?? "";
  return el.innerHTML;
}

// Purview Compliance Manager — display labels for implementation_status and test_status
function purviewImplementationLabel(status) {
  const labels = { notImplemented: "Not implemented", planned: "Planned", alternative: "Alternative implementation", implemented: "Implemented", outOfScope: "Out of scope" };
  return labels[status] || status || "–";
}
function purviewTestLabel(status) {
  const labels = { notAssessed: "Not assessed", none: "None", inProgress: "In progress", partiallyTested: "Partially tested", toBeDetermined: "To be determined", couldNotBeDetermined: "Could not be determined", outOfScope: "Out of scope", failedLowRisk: "Failed (low risk)", failedMediumRisk: "Failed (medium risk)", failedHighRisk: "Failed (high risk)", passed: "Passed" };
  return labels[status] || status || "–";
}

// ═════════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═════════════════════════════════════════════════════════════════════════════

document.addEventListener("DOMContentLoaded", () => {
  loadDashboard();

  $("#refresh-btn").addEventListener("click", loadDashboard);
  $("#department-filter").addEventListener("change", loadDashboard);
  $("#days-filter").addEventListener("change", loadDashboard);
  $("#generate-briefing-btn").addEventListener("click", generateBriefing);
  $("#ask-btn").addEventListener("click", askAdvisor);
  $("#ask-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") askAdvisor();
  });

  // Improvement actions filter handlers
  const filterActions = () => {
    const impactVal = $("#actions-impact-filter").value;
    const statusVal = $("#actions-status-filter").value;
    const allActions = currentData.actions?.actions || [];
    const filtered = allActions.filter((a) => {
      if (impactVal && a.score_impact !== impactVal) return false;
      if (statusVal && a.implementation_status !== statusVal) return false;
      return true;
    });
    renderActionsTable({ actions: filtered });
  };
  $("#actions-impact-filter").addEventListener("change", filterActions);
  $("#actions-status-filter").addEventListener("change", filterActions);

  // Suggested questions (chips)
  $("#ask-suggestions")?.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip?.dataset.question) return;
    const input = $("#ask-input");
    if (input) {
      input.value = chip.dataset.question;
      input.focus();
      askAdvisor();
    }
  });

  // Table sorting (re-render from current data, no reload)
  $$(".data-table--sortable thead th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const table = th.closest("table");
      const tableId = table?.id;
      const key = th.getAttribute("data-sort");
      if (!tableId || !key) return;
      const state = sortState[tableId] || {};
      const nextDir = state.key === key && state.dir === 1 ? -1 : 1;
      sortState[tableId] = { key, dir: nextDir };
      reapplySortAndRenderTables();
    });
  });

  // Copy briefing
  $("#copy-briefing-btn")?.addEventListener("click", () => {
    const content = $("#briefing-content");
    const text = content?.innerText || content?.textContent || "";
    if (!text || text.includes("Click \"Generate Briefing\"")) return;
    navigator.clipboard.writeText(text).then(() => {
      const btn = $("#copy-briefing-btn");
      if (btn) { btn.textContent = "Copied!"; setTimeout(() => { btn.textContent = "Copy"; }, 2000); }
    }).catch(() => {});
  });

  // Demo mode toggle: reload when changed
  $("#demo-mode-toggle")?.addEventListener("change", loadDashboard);

  // KPI cards: click to scroll to related table
  $$(".kpi-card[data-clickable][data-scroll]").forEach((card) => {
    card.addEventListener("click", () => {
      const id = card.getAttribute("data-scroll");
      const el = id ? document.getElementById(id) : null;
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
});
