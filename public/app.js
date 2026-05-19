// ── State ────────────────────────────────────────────────────────────────────
let activeIncident = null;
let lastAnalysisData = null;
let history = [];
let totalQueries = 0;
let totalCost = 0;
let searchTimeout = null;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  document.getElementById('alertForm').addEventListener('submit', handleAnalyze);
  document.getElementById('resolveForm').addEventListener('submit', handleResolve);
  // Ctrl+K / Cmd+K to open command palette
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openCmdPalette(); }
    if (e.key === 'Escape') closeCmdPalette();
  });
});

async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    const count = d.memory_count || d.total_memories || '—';
    document.getElementById('memoryPill').textContent = `● ${count} memories loaded`;
  } catch { document.getElementById('memoryPill').textContent = '● Connected'; }
}

// ── Analyze ──────────────────────────────────────────────────────────────────
async function handleAnalyze(e) {
  e.preventDefault();
  const service = document.getElementById('service').value;
  const error = document.getElementById('error').value.trim();
  const severity = document.getElementById('severity').value;
  if (!error) return alert('Enter an error message.');

  showLoading(true);

  try {
    const r = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_name: service, error_message: error, severity }),
    });
    const data = await r.json();

    activeIncident = { service, error, severity };
    totalQueries++;
    totalCost += data.total_cost || 0;

    history.push({
      time: new Date().toLocaleTimeString('en-US', { hour12: false }),
      service, error: error.slice(0, 60), severity,
      hadMemory: (data.memory_count || 0) > 0,
      model: data.model_used || '—',
      cost: data.total_cost || 0,
    });

    renderResponse(data, severity);
    renderAudit(data, severity);
    renderHistory();
    updateSessionStats();
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    showLoading(false);
  }
}

// ── Render Response ──────────────────────────────────────────────────────────
function renderResponse(data, severity) {
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('responseContent').style.display = 'block';
  lastAnalysisData = data;

  const hasConfidentMatch = data.has_confident_match || false;
  const topConf = data.top_confidence || 0;
  const hasMemory = (data.memory_count || 0) > 0;
  const badgeRow = document.getElementById('badgeRow');

  let badges = `<span class="badge badge-sev sev-${severity}">${severity}</span>`;
  if (hasConfidentMatch) {
    badges += `<span class="badge badge-memory">✓ MEMORY MATCH (${(topConf * 100).toFixed(0)}%)</span>`;
  } else if (hasMemory) {
    badges += `<span class="badge badge-general">⚠ LOW CONFIDENCE (${(topConf * 100).toFixed(0)}%)</span>`;
  } else {
    badges += '<span class="badge badge-general">ℹ NEW ERROR TYPE</span>';
  }
  if (data.pii_scrubbed) badges += '<span class="badge badge-pii">🔒 PII SCRUBBED</span>';
  badges += `<span style="color:#8891a5;font-size:.75rem;margin-left:4px">${activeIncident.service} · ${activeIncident.error.slice(0, 50)}</span>`;
  badgeRow.innerHTML = badges;

  // Memories with confidence scores
  const memories = data.memories || [];
  const expander = document.getElementById('memoriesExpander');
  if (memories.length > 0) {
    expander.style.display = 'block';
    document.getElementById('memCount').textContent = memories.length;
    const list = document.getElementById('memoriesList');
    list.innerHTML = memories.map((m, i) => {
      const text = typeof m === 'string' ? m : m.text;
      const score = typeof m === 'object' ? m.score : 0;
      const pct = (score * 100).toFixed(0);
      const confClass = score >= 0.85 ? 'conf-high' : score >= 0.5 ? 'conf-med' : 'conf-low';
      return `<div class="memory-item">
        <b>Memory #${i + 1}</b> <span class="cmd-result-score">${pct}% match</span>
        <div class="confidence-bar"><div class="confidence-fill ${confClass}" style="width:${pct}%"></div></div>
        <br>${escapeHtml(text)}
      </div>`;
    }).join('');
  } else {
    expander.style.display = 'none';
  }

  const html = markdownToHtml(data.response || 'No response.');
  document.getElementById('agentResponse').innerHTML = html;
  document.getElementById('resolveSection').style.display = 'block';
  document.getElementById('exportBar').style.display = 'flex';
}

// ── Render Audit ─────────────────────────────────────────────────────────────
function renderAudit(data, severity) {
  document.getElementById('auditEmpty').style.display = 'none';
  document.getElementById('auditContent').style.display = 'block';

  const model = data.model_used || '—';
  const isDrafter = model.toLowerCase().includes('8b');
  const tag = document.getElementById('routeTag');
  tag.className = 'route-tag ' + (isDrafter ? 'route-drafter' : 'route-verifier');
  tag.textContent = isDrafter ? '⚡ DRAFTER' : '🔬 VERIFIER';

  const cost = data.total_cost || 0;
  const latency = data.latency_ms || 0;
  const budget = data.severity_budget || 0.25;
  const savings = data.cost_saved_percentage || 0;

  document.getElementById('metricGrid').innerHTML = `
    <div class="m-card full"><div class="m-label">Model</div><div class="m-value m-blue" style="font-size:.8rem;word-break:break-all">${escapeHtml(model)}</div></div>
    <div class="m-card"><div class="m-label">Cost</div><div class="m-value m-green">$${cost.toFixed(6)}</div></div>
    <div class="m-card"><div class="m-label">Latency</div><div class="m-value m-orange">${latency.toFixed(0)}ms</div></div>
    <div class="m-card"><div class="m-label">Budget</div><div class="m-value">$${budget.toFixed(2)}</div></div>
    <div class="m-card"><div class="m-label">Savings</div><div class="m-value ${savings > 0 ? 'm-green' : ''}">${savings.toFixed(1)}%</div></div>
  `;

  const rationales = {
    P1: '🔴 P1 Critical → Escalated to stronger model ($0.50 budget)',
    P2: '🟡 P2 High → Standard budget ($0.25), drafter first',
    P3: '🟢 P3 Medium → Fast/cheap drafter only ($0.10 budget)',
  };
  document.getElementById('rationale').textContent = rationales[severity] || '';

  const trace = data.trace || [];
  const summary = data.summary || {};
  const traceBtn = document.getElementById('traceBtn');
  if (trace.length > 0 || Object.keys(summary).length > 0) {
    traceBtn.style.display = 'block';
    document.getElementById('traceData').textContent = JSON.stringify({ trace, summary }, null, 2);
  } else {
    traceBtn.style.display = 'none';
  }
}

// ── Resolve ──────────────────────────────────────────────────────────────────
async function handleResolve(e) {
  e.preventDefault();
  if (!activeIncident) return;
  const rc = document.getElementById('rootCause').value.trim();
  const fix = document.getElementById('fixApplied').value.trim();
  const by = document.getElementById('resolvedBy').value.trim();
  if (!rc || !fix || !by) return alert('Fill in all fields.');

  const status = document.getElementById('resolveStatus');
  status.innerHTML = '<span style="color:#8891a5">Writing to Hindsight…</span>';

  try {
    const r = await fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service_name: activeIncident.service,
        error_message: activeIncident.error,
        severity: activeIncident.severity,
        root_cause: rc, fix_applied: fix, resolved_by: by,
      }),
    });
    const d = await r.json();
    if (d.success) {
      status.innerHTML = '<span class="success-msg">✅ Memory updated! Run same error again to see agent recall this fix.</span>';
      document.getElementById('resolveForm').reset();
      loadStats();
    } else {
      status.innerHTML = '<span class="error-msg">Failed to write. Check API key.</span>';
    }
  } catch (err) {
    status.innerHTML = `<span class="error-msg">Error: ${err.message}</span>`;
  }
}

// ── History ──────────────────────────────────────────────────────────────────
function renderHistory() {
  if (history.length === 0) return;
  const bar = document.getElementById('historyBar');
  bar.style.display = 'block';
  document.getElementById('historyList').innerHTML = history.slice().reverse().map(h => {
    const icon = h.hadMemory ? '<span class="mem-hit">🟢</span>' : '<span class="mem-miss">🔴</span>';
    return `<div class="history-item">${h.time} ${icon} <b>${h.severity}</b> ${h.service} — ${escapeHtml(h.error)} · ${h.model} · $${h.cost.toFixed(6)}</div>`;
  }).join('');
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function showLoading(show) {
  document.getElementById('loadingState').style.display = show ? 'block' : 'none';
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('responseContent').style.display = show ? 'none' : (activeIncident ? 'block' : 'none');
  document.getElementById('analyzeBtn').disabled = show;
}

function updateSessionStats() {
  const el = document.getElementById('sessionStats');
  el.style.display = 'block';
  document.getElementById('queryCount').textContent = totalQueries;
  document.getElementById('totalCost').textContent = totalCost.toFixed(5);
}

function toggleMemories() {
  const list = document.getElementById('memoriesList');
  const icon = document.getElementById('expandIcon');
  const show = list.style.display === 'none';
  list.style.display = show ? 'block' : 'none';
  icon.textContent = show ? '▾' : '▸';
}

function toggleTrace() {
  const el = document.getElementById('traceData');
  const icon = document.getElementById('traceIcon');
  const show = el.style.display === 'none';
  el.style.display = show ? 'block' : 'none';
  icon.textContent = show ? '▾' : '▸';
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function markdownToHtml(md) {
  return md
    .replace(/### (.*)/g, '<h3>$1</h3>')
    .replace(/## (.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^\- (.*)/gm, '<li>$1</li>')
    .replace(/^\d+\. (.*)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>')
    .replace(/<\/ul>\s*<ul>/g, '')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
}

// ── Command Palette ──────────────────────────────────────────────────────────
function openCmdPalette() {
  document.getElementById('cmdOverlay').classList.add('active');
  setTimeout(() => document.getElementById('cmdInput').focus(), 50);
}

function closeCmdPalette() {
  document.getElementById('cmdOverlay').classList.remove('active');
  document.getElementById('cmdInput').value = '';
  document.getElementById('cmdResults').innerHTML = '<div class="cmd-empty">Type to search Hindsight memory for past incidents</div>';
}

async function searchIncidents(query) {
  clearTimeout(searchTimeout);
  if (query.length < 2) {
    document.getElementById('cmdResults').innerHTML = '<div class="cmd-empty">Type to search Hindsight memory for past incidents</div>';
    return;
  }
  document.getElementById('cmdResults').innerHTML = '<div class="cmd-loading">Searching…</div>';
  searchTimeout = setTimeout(async () => {
    try {
      const r = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service_name: 'search', error_message: query, severity: 'P3' }),
      });
      const data = await r.json();
      const memories = data.memories || [];
      if (memories.length === 0) {
        document.getElementById('cmdResults').innerHTML = '<div class="cmd-empty">No matching incidents found</div>';
        return;
      }
      document.getElementById('cmdResults').innerHTML = memories.map(m => {
        const text = typeof m === 'string' ? m : m.text;
        const score = typeof m === 'object' ? m.score : 0;
        return `<div class="cmd-result-item">
          <span class="cmd-result-score">${(score * 100).toFixed(0)}% match</span><br>
          ${escapeHtml(text.slice(0, 200))}${text.length > 200 ? '…' : ''}
        </div>`;
      }).join('');
    } catch {
      document.getElementById('cmdResults').innerHTML = '<div class="cmd-empty">Search failed</div>';
    }
  }, 500);
}

// ── Export Functions ─────────────────────────────────────────────────────────
function exportRCA() {
  if (!activeIncident || !lastAnalysisData) return;
  const d = lastAnalysisData;
  const now = new Date().toISOString();
  const rca = `# Root Cause Analysis — ${activeIncident.service}

**Generated:** ${now}
**Severity:** ${activeIncident.severity}
**Service:** ${activeIncident.service}
**Error:** ${activeIncident.error}

---

## Agent Analysis

${d.response || 'N/A'}

## Memory Context

- Memories recalled: ${d.memory_count || 0}
- Confidence match: ${d.has_confident_match ? 'Yes' : 'No'} (${((d.top_confidence || 0) * 100).toFixed(0)}%)
- PII scrubbed: ${d.pii_scrubbed ? 'Yes' : 'No'}

## Routing Decision

- Model: ${d.model_used}
- Route: ${d.route_type}
- Cost: $${(d.total_cost || 0).toFixed(6)}
- Latency: ${(d.latency_ms || 0).toFixed(0)}ms
- Budget: $${(d.severity_budget || 0).toFixed(2)}
`;
  downloadFile(`rca-${activeIncident.service}-${Date.now()}.md`, rca, 'text/markdown');
}

function exportAudit() {
  if (!lastAnalysisData) return;
  const payload = {
    exported_at: new Date().toISOString(),
    incident: activeIncident,
    analysis: {
      model: lastAnalysisData.model_used,
      route: lastAnalysisData.route_type,
      cost: lastAnalysisData.total_cost,
      latency_ms: lastAnalysisData.latency_ms,
      budget: lastAnalysisData.severity_budget,
      savings_pct: lastAnalysisData.cost_saved_percentage,
    },
    memory: {
      count: lastAnalysisData.memory_count,
      confident_match: lastAnalysisData.has_confident_match,
      top_confidence: lastAnalysisData.top_confidence,
    },
    pii_scrubbed: lastAnalysisData.pii_scrubbed,
    trace: lastAnalysisData.trace,
    session_history: history,
  };
  downloadFile(`audit-${Date.now()}.json`, JSON.stringify(payload, null, 2), 'application/json');
}

function downloadFile(name, content, type) {
  const blob = new Blob([content], { type });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}
