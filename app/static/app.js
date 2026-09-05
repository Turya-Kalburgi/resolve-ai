// ResolveAI — Premium Fintech Dashboard Controller
let activeFilter = 'ALL';
let searchQuery = '';
let auditLogs = [];
let metricsPayload = null;
let lastRunTimestamp = null;
let currentView = 'overview';

document.addEventListener('DOMContentLoaded', () => {
  loadData();
  rotateFinanceQuote();
  setInterval(rotateFinanceQuote, 120000);
});

function rotateFinanceQuote() {
  if (typeof getRandomFinanceQuote !== 'function') return;
  const quoteObj = getRandomFinanceQuote();
  if (!quoteObj) return;

  const box = document.querySelector('.finance-insight-box');
  const txtEl = document.getElementById('financeQuoteText');
  const authEl = document.getElementById('financeQuoteAuthor');

  if (box && txtEl && authEl) {
    box.style.opacity = '0.3';
    setTimeout(() => {
      txtEl.textContent = `"${quoteObj.quote}"`;
      authEl.textContent = `— ${quoteObj.author}`;
      box.style.opacity = '1';
    }, 200);
  }
}

function switchView(viewName) {
  currentView = viewName;
  document.querySelectorAll('.tab-view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) {
    targetView.classList.add('active');
  }

  // Highlight active nav tab
  const activeNavItem = Array.from(document.querySelectorAll('.nav-item')).find(el =>
    el.getAttribute('onclick') && el.getAttribute('onclick').includes(viewName)
  );
  if (activeNavItem) {
    activeNavItem.classList.add('active');
  }

  if (viewName === 'analytics' && metricsPayload) {
    renderAnalyticsCharts();
  } else if (viewName === 'audit') {
    renderAuditTable();
  } else if (viewName === 'benchmark' && metricsPayload) {
    renderBenchmarkView();
  }
}

async function loadData() {
  try {
    showToast('Fetching latest backend telemetry...', 'info');

    const [metricsRes, logsRes] = await Promise.all([
      fetch('/metrics/summary'),
      fetch('/audit/logs?limit=100')
    ]);

    if (!metricsRes.ok || !logsRes.ok) {
      throw new Error('Failed to connect to ResolveAI backend service.');
    }

    metricsPayload = await metricsRes.json();
    const logsData = await logsRes.json();
    auditLogs = logsData.logs || [];

    renderHeroAndMetrics(metricsPayload);
    renderOutcomeCards(metricsPayload.by_currency || {});
    renderCasesTable();
    renderAnalyticsCharts();
    renderAuditTable();
    renderBenchmarkView();

    if (!lastRunTimestamp && auditLogs.length > 0) {
      lastRunTimestamp = new Date(auditLogs[0].created_at).toLocaleTimeString();
    }

    document.getElementById('lastRunTime').textContent = `Last run: ${lastRunTimestamp || 'Just now'}`;
    showToast('Dashboard updated from backend API telemetry.', 'info');
    setTimeout(hideToast, 2500);
  } catch (err) {
    showToast(`Telemetry Error: ${err.message}`, 'error');
  }
}

function animateCountUp(elementId, targetValue, prefix = '', suffix = '', decimals = 0, duration = 800, delay = 0) {
  const el = document.getElementById(elementId);
  if (!el) return;

  const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced) {
    el.textContent = `${prefix}${targetValue.toFixed(decimals)}${suffix}`;
    return;
  }

  setTimeout(() => {
    let startTimestamp = null;
    const startVal = 0;

    function step(timestamp) {
      if (!startTimestamp) startTimestamp = timestamp;
      const progress = Math.min((timestamp - startTimestamp) / duration, 1);
      const eased = 1 - (1 - progress) * (1 - progress);
      const currentVal = startVal + (targetValue - startVal) * eased;

      el.textContent = `${prefix}${currentVal.toFixed(decimals)}${suffix}`;

      if (progress < 1) {
        window.requestAnimationFrame(step);
      } else {
        el.textContent = `${prefix}${targetValue.toFixed(decimals)}${suffix}`;
      }
    }

    window.requestAnimationFrame(step);
  }, delay);
}

function renderHeroAndMetrics(metrics) {
  const byCurr = metrics.by_currency || {};

  // Compute Hero Counts
  let totalEvaluated = metrics.overall_payments_evaluated || 0;
  let totalRecovered = 0;
  let totalEscalated = 0;
  let totalBlocked = 0;
  let totalAttempts = 0;

  Object.values(byCurr).forEach(c => {
    totalRecovered += c.successful_recoveries_count || 0;
    totalEscalated += c.escalated_cases_count || 0;
    totalBlocked += c.blocked_cases_count || 0;
    totalAttempts += (c.successful_recoveries_count || 0) + (c.failed_recoveries_count || 0);
  });

  // Animate Hero KPI Numbers (Count-up from 0 to returned API integer)
  animateCountUp('heroAnalyzed', totalEvaluated, '', '', 0, 700, 0);
  animateCountUp('heroRecovered', totalRecovered, '', '', 0, 700, 100);
  animateCountUp('heroEscalated', totalEscalated, '', '', 0, 700, 200);
  animateCountUp('heroBlocked', totalBlocked, '', '', 0, 700, 300);
  document.getElementById('heroCasesFoot').textContent = `${totalEvaluated} payment-risk cases analyzed`;

  // Analytics KPI Row
  const elTotal = document.getElementById('analyticsKpiTotal');
  if (elTotal) elTotal.textContent = totalEvaluated;
  const elRec = document.getElementById('analyticsKpiRecovered');
  if (elRec) elRec.textContent = totalRecovered;
  const elAtt = document.getElementById('analyticsKpiAttempts');
  if (elAtt) elAtt.textContent = totalAttempts;
  const elBlk = document.getElementById('analyticsKpiBlocked');
  if (elBlk) elBlk.textContent = totalBlocked;
  const elEsc = document.getElementById('analyticsKpiEscalated');
  if (elEsc) elEsc.textContent = totalEscalated;

  // Audit KPI Bar
  const auditTot = document.getElementById('auditKpiTotal');
  if (auditTot) auditTot.textContent = auditLogs.length || totalEvaluated;
  const auditEval = document.getElementById('auditKpiEvaluated');
  if (auditEval) auditEval.textContent = totalEvaluated;
  const auditEsc = document.getElementById('auditKpiEscalated');
  if (auditEsc) auditEsc.textContent = totalEscalated;

  // Render & Animate Currency-Separated Recovered Boxes (NEVER SUM CURRENCIES)
  const usd = byCurr['USD'] || { total_revenue_recovered: 0 };
  const eur = byCurr['EUR'] || { total_revenue_recovered: 0 };
  const gbp = byCurr['GBP'] || { total_revenue_recovered: 0 };
  const cad = byCurr['CAD'] || { total_revenue_recovered: 0 };

  animateCountUp('recUSD', usd.total_revenue_recovered, '+$', '', 2, 850, 0);
  animateCountUp('recEUR', eur.total_revenue_recovered, '+€', '', 2, 850, 120);
  animateCountUp('recGBP', gbp.total_revenue_recovered, '+£', '', 2, 850, 240);
  animateCountUp('recCAD', cad.total_revenue_recovered, '+$', '', 2, 850, 360);

  // Render Revenue at Risk by Currency Table
  const tbody = document.getElementById('riskTableBody');
  if (tbody) {
    tbody.innerHTML = '';
    const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };

    Object.keys(byCurr).sort().forEach(code => {
      const c = byCurr[code];
      const sym = symbolMap[code] || '';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 700;">${c.currency}</td>
        <td>${sym}${c.total_revenue_at_risk.toFixed(2)}</td>
        <td style="color: var(--status-recovered); font-weight: 600;">→ ${sym}${c.total_revenue_recovered.toFixed(2)}</td>
        <td><span class="rate-badge">${c.recovery_rate_percentage.toFixed(2)}%</span></td>
      `;
      tbody.appendChild(tr);
    });
  }
}

function renderOutcomeCards(byCurr) {
  const container = document.getElementById('outcomeCardsGrid');
  if (!container) return;
  container.innerHTML = '';

  const totals = {
    RECOVERED: 0,
    FAILED: 0,
    BLOCKED: 0,
    ESCALATED: 0,
    MONITORING: 0,
    NO_ACTION: 0
  };

  Object.values(byCurr).forEach(c => {
    totals.RECOVERED += c.successful_recoveries_count || 0;
    totals.FAILED += c.failed_recoveries_count || 0;
    totals.BLOCKED += c.blocked_cases_count || 0;
    totals.ESCALATED += c.escalated_cases_count || 0;
    totals.MONITORING += c.monitored_cases_count || 0;
    totals.NO_ACTION += c.no_action_cases_count || 0;
  });

  const labels = {
    RECOVERED: 'Recovered',
    FAILED: 'Failed',
    BLOCKED: 'Blocked',
    ESCALATED: 'Escalated',
    MONITORING: 'Monitoring',
    NO_ACTION: 'No Action'
  };

  Object.keys(totals).forEach(key => {
    const card = document.createElement('div');
    card.className = 'outcome-card';
    card.innerHTML = `
      <span class="outcome-name">${labels[key]}</span>
      <span class="outcome-val">${totals[key]}</span>
    `;
    container.appendChild(card);
  });
}

function renderCasesTable() {
  const tbody = document.getElementById('casesTableBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };
  const actionLabelMap = {
    PROMPT_RETRY: 'Prompt Customer Retry',
    HUMAN_REVIEW: 'Human Review',
    STATUS_MONITOR: 'Monitor Settlement',
    NO_OP: 'No Action Required'
  };

  const filtered = auditLogs.filter(log => {
    const matchesFilter = (activeFilter === 'ALL') || (log.workflow_outcome === activeFilter);
    const q = searchQuery.toLowerCase();
    const matchesQuery = !q || (
      log.payment_id.toLowerCase().includes(q) ||
      log.customer_id.toLowerCase().includes(q) ||
      log.amount.toString().includes(q)
    );
    return matchesFilter && matchesQuery;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No payment cases matching criteria.</td></tr>`;
    return;
  }

  filtered.forEach(log => {
    const sym = symbolMap[log.currency] || '';
    const displayAction = actionLabelMap[log.action_type] || log.action_type;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-weight: 700; font-family: monospace;">${log.payment_id}</td>
      <td style="font-weight: 600;">${sym}${log.amount.toFixed(2)}</td>
      <td>${log.currency}</td>
      <td><span style="color: var(--text-muted);">${log.initial_payment_status}</span></td>
      <td style="font-weight: 500;">${displayAction}</td>
      <td><span class="badge badge-${log.policy_decision}">${log.policy_decision}</span></td>
      <td><span class="badge badge-${log.workflow_outcome}">${log.workflow_outcome}</span></td>
      <td style="font-weight: 700; color: ${log.recovered_amount > 0 ? 'var(--status-recovered)' : 'var(--text-muted)'}">
        ${log.recovered_amount > 0 ? '+' + sym + log.recovered_amount.toFixed(2) : sym + '0.00'}
      </td>
      <td>
        <button class="btn-inspect-link" onclick="showTrace('${log.payment_id}')">View Trace →</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function renderAnalyticsCharts() {
  if (!metricsPayload) return;
  const byCurr = metricsPayload.by_currency || {};

  // Compute Core Telemetry Counts
  let totalEvaluated = metricsPayload.overall_payments_evaluated || 0;
  let totalRecovered = 0;
  let totalBlocked = 0;
  let totalEscalated = 0;
  let totalAttempts = 0;

  Object.values(byCurr).forEach(c => {
    totalRecovered += c.successful_recoveries_count || 0;
    totalBlocked += c.blocked_cases_count || 0;
    totalEscalated += c.escalated_cases_count || 0;
    totalAttempts += (c.successful_recoveries_count || 0) + (c.failed_recoveries_count || 0);
  });

  const approvedCount = totalEvaluated - totalBlocked - totalEscalated;

  // 1. MAIN CHART: Recovery Pipeline Progression (SVG Trend Chart)
  const pipelineBox = document.getElementById('chartPipelineProgression');
  if (pipelineBox) {
    pipelineBox.innerHTML = `
      <svg viewBox="0 0 800 180" style="width: 100%; height: 180px; overflow: visible;">
        <defs>
          <linearGradient id="pipelineLineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#2C365A" />
            <stop offset="100%" stop-color="#1B4D3E" />
          </linearGradient>
        </defs>

        <path d="M 80 40 L 240 40 L 400 80 L 560 115 L 720 135" fill="none" stroke="url(#pipelineLineGrad)" stroke-width="3" stroke-linecap="round" />

        <g transform="translate(80, 40)">
          <circle r="7" fill="#FAF7F2" stroke="#2C365A" stroke-width="3" />
          <text y="-18" text-anchor="middle" font-family="'Newsreader', Georgia, serif" font-size="16" font-weight="700" fill="#2C365A">${totalEvaluated}</text>
          <text y="28" text-anchor="middle" font-size="11" font-weight="700" fill="#5C6684">01 FAILURE</text>
          <text y="42" text-anchor="middle" font-size="10" fill="#8C96B4">Revenue at Risk</text>
        </g>

        <g transform="translate(240, 40)">
          <circle r="7" fill="#FAF7F2" stroke="#2C365A" stroke-width="3" />
          <text y="-18" text-anchor="middle" font-family="'Newsreader', Georgia, serif" font-size="16" font-weight="700" fill="#2C365A">${totalEvaluated}</text>
          <text y="28" text-anchor="middle" font-size="11" font-weight="700" fill="#5C6684">02 AI DIAGNOSIS</text>
          <text y="42" text-anchor="middle" font-size="10" fill="#8C96B4">Opportunities</text>
        </g>

        <g transform="translate(400, 80)">
          <circle r="7" fill="#FAF7F2" stroke="#2C365A" stroke-width="3" />
          <text y="-18" text-anchor="middle" font-family="'Newsreader', Georgia, serif" font-size="16" font-weight="700" fill="#2C365A">${approvedCount}</text>
          <text y="28" text-anchor="middle" font-size="11" font-weight="700" fill="#5C6684">03 SAFETY GATE</text>
          <text y="42" text-anchor="middle" font-size="10" fill="#8C96B4">Approved Actions</text>
        </g>

        <g transform="translate(560, 115)">
          <circle r="7" fill="#FAF7F2" stroke="#2C365A" stroke-width="3" />
          <text y="-18" text-anchor="middle" font-family="'Newsreader', Georgia, serif" font-size="16" font-weight="700" fill="#2C365A">${totalAttempts}</text>
          <text y="28" text-anchor="middle" font-size="11" font-weight="700" fill="#5C6684">04 EXECUTION</text>
          <text y="42" text-anchor="middle" font-size="10" fill="#8C96B4">Retries Attempted</text>
        </g>

        <g transform="translate(720, 135)">
          <circle r="8" fill="#FAF7F2" stroke="#1B4D3E" stroke-width="3" />
          <text y="-18" text-anchor="middle" font-family="'Newsreader', Georgia, serif" font-size="18" font-weight="700" fill="#1B4D3E">+${totalRecovered}</text>
          <text y="28" text-anchor="middle" font-size="11" font-weight="700" fill="#1B4D3E">05 RECOVERED</text>
          <text y="42" text-anchor="middle" font-size="10" fill="#1B4D3E">Final Outcome</text>
        </g>
      </svg>
    `;
  }

  // Refined Editorial Pastel Color Palette for Lower Vertical Bar Charts
  const pastelMapRev = {
    CAD: '#7CA982', // Soft Sage Green
    EUR: '#7B9EA8', // Soft Dusty Blue
    GBP: '#5C768D', // Soft Pastel Deep Blue
    USD: '#588B76'  // Soft Muted Green
  };

  const pastelMapRate = {
    CAD: '#8CA4BE', // Soft Dusty Light Blue
    EUR: '#6B819C', // Soft Muted Indigo
    GBP: '#5C768D', // Soft Pastel Deep Blue
    USD: '#7CA982'  // Soft Sage
  };

  // 2. SUPPORTING CHART A: Recovered Revenue by Currency (Clean Vertical Bars)
  const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };
  const chartRev = document.getElementById('chartVerticalRevenue');
  if (chartRev) {
    const sortedCurrs = Object.keys(byCurr).sort();
    const maxRec = Math.max(...sortedCurrs.map(k => byCurr[k].total_revenue_recovered), 1);
    chartRev.innerHTML = sortedCurrs.map(code => {
      const c = byCurr[code];
      const val = c.total_revenue_recovered;
      const heightPx = Math.max(Math.round((val / maxRec) * 130), 12);
      const sym = symbolMap[code] || '';
      const barColor = pastelMapRev[code] || '#7CA982';
      return `
        <div class="vert-bar-col">
          <span class="vert-bar-val">+${sym}${val.toFixed(2)}</span>
          <div class="vert-bar-rect" style="height: ${heightPx}px; background: ${barColor};"></div>
          <span class="vert-bar-label">${code}</span>
        </div>
      `;
    }).join('');
  }

  // 3. SUPPORTING CHART B: Recovery Rate by Currency (Clean Vertical Bars)
  const chartRate = document.getElementById('chartVerticalRate');
  if (chartRate) {
    const sortedCurrs = Object.keys(byCurr).sort();
    chartRate.innerHTML = sortedCurrs.map(code => {
      const c = byCurr[code];
      const val = c.recovery_rate_percentage;
      const heightPx = Math.max(Math.round((val / 100) * 130), 12);
      const barColor = pastelMapRate[code] || '#6B819C';
      return `
        <div class="vert-bar-col">
          <span class="vert-bar-val">${val.toFixed(2)}%</span>
          <div class="vert-bar-rect" style="height: ${heightPx}px; background: ${barColor};"></div>
          <span class="vert-bar-label">${code}</span>
        </div>
      `;
    }).join('');
  }

  // 4. SAFETY SECTION: Safety Gatekeeper Decisions
  const chartSafety = document.getElementById('chartSafetyDecisionsCol');
  if (chartSafety) {
    const maxVal = Math.max(approvedCount, totalBlocked, totalEscalated, 1);
    const approvedPx = Math.max(Math.round((approvedCount / maxVal) * 110), 12);
    const blockedPx = Math.max(Math.round((totalBlocked / maxVal) * 110), 12);
    const escalatedPx = Math.max(Math.round((totalEscalated / maxVal) * 110), 12);

    chartSafety.innerHTML = `
      <div class="vert-bar-col">
        <span class="vert-bar-val" style="color: var(--status-recovered);">${approvedCount}</span>
        <div class="vert-bar-rect" style="height: ${approvedPx}px; background: #7CA982;"></div>
        <span class="vert-bar-label" style="color: var(--status-recovered);">APPROVED</span>
      </div>
      <div class="vert-bar-col">
        <span class="vert-bar-val" style="color: var(--status-blocked);">${totalBlocked}</span>
        <div class="vert-bar-rect" style="height: ${blockedPx}px; background: #D98282;"></div>
        <span class="vert-bar-label" style="color: var(--status-blocked);">BLOCKED</span>
      </div>
      <div class="vert-bar-col">
        <span class="vert-bar-val" style="color: var(--status-escalated);">${totalEscalated}</span>
        <div class="vert-bar-rect" style="height: ${escalatedPx}px; background: #E2A06E;"></div>
        <span class="vert-bar-label" style="color: var(--status-escalated);">ESCALATED</span>
      </div>
    `;
  }
}

function safeNum(val, decimals = 2) {
  if (val === undefined || val === null || isNaN(val)) return '—';
  return Number(val).toFixed(decimals);
}

function renderBenchmarkView() {
  if (!metricsPayload) return;
  const byCurr = metricsPayload.by_currency || {};

  let totalEvaluated = metricsPayload.overall_payments_evaluated || 0;
  let totalRecovered = 0;
  let totalFailed = 0;
  let totalBlocked = 0;
  let totalEscalated = 0;

  Object.values(byCurr).forEach(c => {
    totalRecovered += c.successful_recoveries_count || 0;
    totalFailed += c.failed_recoveries_count || 0;
    totalBlocked += c.blocked_cases_count || 0;
    totalEscalated += c.escalated_cases_count || 0;
  });

  const bmEval = document.getElementById('bmKpiEvaluated');
  if (bmEval) bmEval.textContent = totalEvaluated;
  const bmRec = document.getElementById('bmKpiRecovered');
  if (bmRec) bmRec.textContent = totalRecovered;
  const bmFail = document.getElementById('bmKpiFailed');
  if (bmFail) bmFail.textContent = totalFailed;
  const bmBlk = document.getElementById('bmKpiBlocked');
  if (bmBlk) bmBlk.textContent = totalBlocked;
  const bmEsc = document.getElementById('bmKpiEscalated');
  if (bmEsc) bmEsc.textContent = totalEscalated;

  // Render Benchmark Currency Performance Table
  const tbody = document.getElementById('bmCurrencyTableBody');
  if (tbody) {
    tbody.innerHTML = '';
    const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };

    Object.keys(byCurr).sort().forEach(code => {
      const c = byCurr[code];
      const sym = symbolMap[code] || '';
      const escRate = c.human_escalation_rate_percentage ?? c.escalation_rate_percentage;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td style="font-weight: 700;">${c.currency}</td>
        <td>${c.total_payments_evaluated}</td>
        <td>${sym}${safeNum(c.total_revenue_at_risk)}</td>
        <td style="color: var(--status-recovered); font-weight: 700;">+${sym}${safeNum(c.total_revenue_recovered)}</td>
        <td><span class="rate-badge">${safeNum(c.recovery_rate_percentage)}%</span></td>
        <td><span style="font-weight: 600; color: var(--status-recovered);">${safeNum(c.recovery_success_rate_percentage)}%</span></td>
        <td><span style="font-weight: 600; color: var(--status-blocked);">${safeNum(c.policy_block_rate_percentage)}%</span></td>
        <td><span style="font-weight: 600; color: var(--status-escalated);">${safeNum(escRate)}%</span></td>
      `;
      tbody.appendChild(tr);
    });
  }
}

function renderAuditTable() {
  const tbody = document.getElementById('auditTableBodyView');
  if (!tbody) return;
  tbody.innerHTML = '';

  const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };
  const actionLabelMap = {
    PROMPT_RETRY: 'Prompt Customer Retry',
    HUMAN_REVIEW: 'Human Review',
    STATUS_MONITOR: 'Monitor Settlement',
    NO_OP: 'No Action Required'
  };

  if (auditLogs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 32px;">No audit records available.</td></tr>`;
    return;
  }

  auditLogs.forEach(log => {
    const sym = symbolMap[log.currency] || '';
    const displayAction = actionLabelMap[log.action_type] || log.action_type;
    const timeStr = new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td style="font-size: 12px; color: var(--text-muted); font-family: monospace;">${timeStr}</td>
      <td style="font-weight: 700; font-family: monospace;">${log.payment_id}</td>
      <td><span style="font-weight: 600;">${log.risk_level}</span></td>
      <td style="font-weight: 500;">${displayAction}</td>
      <td>${Math.round(log.ai_confidence_score * 100)}%</td>
      <td><span class="badge badge-${log.policy_decision}">${log.policy_decision}</span></td>
      <td><span class="badge badge-${log.workflow_outcome}">${log.workflow_outcome}</span></td>
      <td style="font-weight: 700; color: ${log.recovered_amount > 0 ? 'var(--status-recovered)' : 'var(--text-muted)'}">
        ${log.recovered_amount > 0 ? '+' + sym + log.recovered_amount.toFixed(2) : sym + '0.00'}
      </td>
      <td>
        <button class="btn-inspect-link" onclick="showTrace('${log.payment_id}')">View Audit Trail →</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function setFilter(filter) {
  activeFilter = filter;
  document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.toUpperCase().includes(filter));
  });
  renderCasesTable();
}

function handleSearch() {
  searchQuery = document.getElementById('searchBox').value.trim();
  renderCasesTable();
}

function filterByPaymentId(paymentId) {
  const searchBox = document.getElementById('searchBox');
  if (searchBox) {
    searchBox.value = paymentId;
    handleSearch();
  }
  closeTraceDrawer();
  switchView('cases');
}

function filterDemoArchetype(paymentId) {
  switchView('cases');
  const searchBox = document.getElementById('searchBox');
  if (searchBox) {
    searchBox.value = paymentId;
    handleSearch();
  }
  inspectTrace(paymentId);
}

function showTrace(paymentId) {
  inspectTrace(paymentId);
}

function inspectTrace(paymentId) {
  const log = auditLogs.find(l => l.payment_id === paymentId);
  if (!log) return;

  const symbolMap = { USD: '$', EUR: '€', GBP: '£', CAD: '$' };
  const sym = symbolMap[log.currency] || '';
  const actionLabelMap = {
    PROMPT_RETRY: 'Prompt Customer Retry',
    HUMAN_REVIEW: 'Human Review',
    STATUS_MONITOR: 'Monitor Settlement',
    NO_OP: 'No Action Required'
  };

  const humanAction = actionLabelMap[log.action_type] || log.action_type;
  const confPct = Math.round(log.ai_confidence_score * 100);

  const titleEl = document.getElementById('drawerPaymentTitle');
  if (titleEl) titleEl.textContent = `Payment Trace: ${log.payment_id}`;
  const metaEl = document.getElementById('drawerPaymentMeta');
  if (metaEl) metaEl.textContent = `${sym}${log.amount.toFixed(2)} ${log.currency} · Customer: ${log.customer_id} · Audit ID: ${log.id}`;

  const body = document.getElementById('drawerBody');

  // Step 4 Policy Summary Statement
  let policyHeadline = "The AI can recommend an action. It cannot override the safety layer.";
  let policyDetailText = log.policy_primary_reason || `${log.policy_decision} by Policy Safety Engine`;
  if (log.policy_decision === 'APPROVED') {
    policyDetailText = `6/6 deterministic safety policy rules passed cleanly.`;
  }

  // Step 5 Workflow Outcome Styling & Statement
  let outcomeBoxStyle = "background: var(--surface-card); border: 1px solid var(--border-color);";
  let outcomeHeader = `Outcome: ${log.workflow_outcome}`;
  let outcomeDetail = `Payment recovery process finished with status '${log.new_payment_status}'.`;

  if (log.workflow_outcome === 'RECOVERED') {
    outcomeBoxStyle = "background: var(--status-recovered-bg); border: 1px solid var(--status-recovered-border);";
    outcomeHeader = `✓ RECOVERED: +${sym}${log.recovered_amount.toFixed(2)}`;
    outcomeDetail = `Simulated payment recovery completed successfully. Revenue recovered: +${sym}${log.recovered_amount.toFixed(2)}.`;
  } else if (log.workflow_outcome === 'BLOCKED') {
    outcomeBoxStyle = "background: var(--status-blocked-bg); border: 1px solid var(--status-blocked-border);";
    outcomeHeader = `🛑 BLOCKED: $0.00 Recovered`;
    outcomeDetail = `Recovery action BLOCKED by Policy Safety Engine (${log.policy_primary_reason}). Zero financial risk executed.`;
  } else if (log.workflow_outcome === 'ESCALATED') {
    outcomeBoxStyle = "background: var(--status-escalated-bg); border: 1px solid var(--status-escalated-border);";
    outcomeHeader = `⚠️ ESCALATED: $0.00 Recovered`;
    outcomeDetail = `Payment ESCALATED for mandatory human review. Automated execution halted.`;
  }

  const timelineHtml = `
    <div class="timeline">

      <!-- Step 1: Input -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">1</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card">
          <div class="step-header">
            <span class="step-name">1. PAYMENT INPUT</span>
            <span class="badge badge-FAILED">Status: ${log.initial_payment_status}</span>
          </div>
          <div style="font-size: 16px; font-weight: 700; color: var(--text-ocean);">
            ${sym}${log.amount.toFixed(2)} ${log.currency}
          </div>
          <div style="font-size: 13px; color: var(--text-muted);">
            Customer: ${log.customer_id} · Merchant: ${log.merchant_id}
          </div>
        </div>
      </div>

      <!-- Step 2: Risk Diagnosis -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">2</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card">
          <div class="step-header">
            <span class="step-name">2. RISK DIAGNOSIS</span>
            <span class="badge badge-FAILED">${log.risk_category}</span>
          </div>
          <div style="font-size: 14px; font-weight: 600; color: var(--text-ocean);">
            Risk Level: ${log.risk_level} (${(log.risk_score * 100).toFixed(0)}% Score)
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            ${(log.risk_reasons || []).join('; ')}
          </div>
        </div>
      </div>

      <!-- Step 3: AI Recovery Agent -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">3</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card">
          <div class="step-header">
            <span class="step-name">3. AI RECOVERY AGENT</span>
            <span style="font-size: 12px; font-weight: 700; color: var(--status-monitoring);">Confidence: ${confPct}%</span>
          </div>
          <div style="font-size: 15px; font-weight: 700; color: var(--text-ocean);">
            Recommendation: ${humanAction}
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            Strategy: ${log.recommended_strategy} (${log.action_type})
          </div>
          
          <div class="collapsible-trigger" onclick="toggleCollapsible('aiReasoningBox')">
            ▶ View AI Reasoning Breakdown
          </div>
          <div id="aiReasoningBox" class="collapsible-box" style="display: none;">${log.ai_explanation}</div>

          ${log.suggested_customer_message ? `
            <div style="margin-top: 6px; font-size: 12px; color: var(--text-muted);">
              <strong>Suggested Customer Message:</strong> "${log.suggested_customer_message}"
            </div>
          ` : ''}
        </div>
      </div>

      <!-- Step 4: Safety Gatekeeper -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">4</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card" style="border: 2px solid ${log.policy_decision === 'APPROVED' ? 'var(--status-recovered-border)' : log.policy_decision === 'BLOCKED' ? 'var(--status-blocked-border)' : 'var(--status-escalated-border)'};">
          <div class="step-header">
            <span class="step-name">4. SAFETY GATEKEEPER</span>
            <span class="badge badge-${log.policy_decision}">${log.policy_decision}</span>
          </div>
          <div style="font-family: var(--font-serif); font-size: 15px; font-weight: 600; color: var(--text-ocean);">
            "${policyHeadline}"
          </div>
          <div style="font-size: 13px; font-weight: 700; color: var(--text-ocean); margin-top: 4px;">
            Policy Rule: ${policyDetailText}
          </div>
          
          <div class="collapsible-trigger" onclick="toggleCollapsible('policyRulesBox')">
            ▶ View Technical Rule Details (6 Rules)
          </div>
          <div id="policyRulesBox" class="collapsible-box" style="display: none;">${JSON.stringify(log.policy_rules_evaluated, null, 2)}</div>
        </div>
      </div>

      <!-- Step 5: Workflow Execution -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">5</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card" style="${outcomeBoxStyle}">
          <div class="step-header">
            <span class="step-name">5. WORKFLOW EXECUTION</span>
            <span class="badge badge-${log.workflow_outcome}">${log.workflow_outcome}</span>
          </div>
          <div style="font-family: var(--font-serif); font-size: 20px; font-weight: 700; color: var(--text-ocean);">
            ${outcomeHeader}
          </div>
          <div style="font-size: 13px; color: var(--text-muted);">
            ${outcomeDetail}
          </div>
        </div>
      </div>

      <!-- Step 6: Audit Trail -->
      <div class="timeline-step">
        <div class="step-marker">
          <div class="step-circle">6</div>
          <div class="step-line"></div>
        </div>
        <div class="step-card">
          <div class="step-header">
            <span class="step-name">6. AUDIT TRAIL</span>
            <span style="font-size: 11px; color: var(--text-muted);">Persisted Log</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted);">
            Log ID: <span style="font-family: monospace; font-weight: 600;">${log.id}</span><br>
            Timestamp: ${new Date(log.created_at).toLocaleString()}
          </div>
          <div style="margin-top: 10px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
            <button class="btn-inspect-link" onclick="filterByPaymentId('${log.payment_id}')">
              Filter Table by Payment ID →
            </button>
          </div>
        </div>
      </div>

    </div>
  `;

  if (body) {
    body.innerHTML = timelineHtml;
  }

  const overlay = document.getElementById('traceOverlay');
  if (overlay) {
    overlay.style.cssText = "display: flex !important; visibility: visible !important; opacity: 1 !important; pointer-events: auto !important; position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important; bottom: 0 !important; z-index: 999999 !important; background: rgba(44, 54, 90, 0.4) !important;";
    overlay.classList.add('active');
    const drawer = overlay.querySelector('.trace-drawer');
    if (drawer) {
      drawer.style.cssText = "transform: translateX(0) !important; opacity: 1 !important; visibility: visible !important; display: flex !important; background: #EEE8DF !important;";
    }
  }

  // Standalone guaranteed emergency modal attached directly to document.body
  const existingModal = document.getElementById('emergencyTraceModal');
  if (existingModal) {
    existingModal.remove();
  }

  const modal = document.createElement('div');
  modal.id = 'emergencyTraceModal';
  modal.style.cssText = "position: fixed !important; top: 0 !important; right: 0 !important; width: 640px !important; max-width: 90vw !important; height: 100vh !important; z-index: 2147483647 !important; background: #EEE8DF !important; color: #2C365A !important; overflow-y: auto !important; padding: 28px !important; box-sizing: border-box !important; box-shadow: -10px 0 40px rgba(0,0,0,0.3) !important; font-family: system-ui, -apple-system, sans-serif !important;";

  modal.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #D4CEB8; padding-bottom: 16px; margin-bottom: 20px;">
      <div>
        <div style="font-family: Georgia, serif; font-size: 22px; font-weight: 700; color: #2C365A;">Payment Trace: ${log.payment_id}</div>
        <div style="font-size: 13px; color: #5C6684; margin-top: 4px;">${sym}${log.amount.toFixed(2)} ${log.currency} · Customer: ${log.customer_id} · Audit ID: ${log.id}</div>
      </div>
      <button onclick="closeTraceDrawer()" style="background: #2C365A; color: #FAF7F2; border: none; border-radius: 6px; padding: 8px 16px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.15);">✕ CLOSE TRACE</button>
    </div>
    ${timelineHtml}
  `;

  document.body.appendChild(modal);
}

function toggleCollapsible(id) {
  const el = document.getElementById(id);
  if (el) {
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }
}

function closeTraceDrawer() {
  const modal = document.getElementById('emergencyTraceModal');
  if (modal) {
    modal.remove();
  }

  const overlay = document.getElementById('traceOverlay');
  if (overlay) {
    overlay.style.cssText = "display: none !important; opacity: 0 !important; pointer-events: none !important;";
    overlay.classList.remove('active');
    const drawer = overlay.querySelector('.trace-drawer');
    if (drawer) {
      drawer.style.cssText = "transform: translateX(100%) !important;";
    }
  }
}

function closeTraceOnOverlay(e) {
  if (e.target.id === 'traceOverlay') {
    closeTraceDrawer();
  }
}

window.showTrace = showTrace;
window.inspectTrace = inspectTrace;

async function runBatchEvaluation() {
  const btn = document.getElementById('btnRunSimulation');
  btn.disabled = true;
  btn.innerHTML = '<span>Running simulation…</span>';
  showToast('Executing 30-Payment Simulation across Phases 1–6...', 'info');

  const progressTimer = setTimeout(() => {
    if (btn.disabled) {
      btn.innerHTML = '<span>Processing 30 payment cases…</span>';
    }
  }, 600);

  try {
    const res = await fetch('/payments/evaluate-batch?reset_db=true', { method: 'POST' });
    if (!res.ok) {
      throw new Error('Simulation execution failed.');
    }
    const data = await res.json();
    clearTimeout(progressTimer);

    lastRunTimestamp = new Date().toLocaleTimeString();
    document.getElementById('lastRunTime').textContent = `Last run: ${lastRunTimestamp}`;

    btn.innerHTML = '<span>✓ 30 payments processed</span>';
    showToast(`✓ Simulation completed! Evaluated ${data.total_payments_processed} payments in ${data.execution_time_seconds}s.`, 'info');
    await loadData();
  } catch (err) {
    clearTimeout(progressTimer);
    showToast(`Simulation Error: ${err.message}`, 'error');
  } finally {
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = '<span>Run 30-Payment Simulation →</span>';
    }, 2000);
  }
}

function showToast(msg, type) {
  const toast = document.getElementById('alertToast');
  toast.className = `alert-toast active alert-toast-${type}`;
  toast.textContent = msg;
}

function hideToast() {
  const toast = document.getElementById('alertToast');
  toast.className = 'alert-toast';
}
