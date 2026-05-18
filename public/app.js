// ── State ────────────────────────────────────────────────────────────────────
let activeIncident = null;
let history = [];
let totalQueries = 0;
let totalCost = 0;

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  document.getElementById('alertForm').addEventListener('submit', handleAnalyze);
  document.getElementById('resolveForm').addEventListener('submit', handleResolve);
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

  const hasMemory = (data.memory_count || 0) > 0;
  const badgeRow = document.getElementById('badgeRow');
  badgeRow.innerHTML =
    `<span class="badge badge-sev sev-${severity}">${severity}</span>` +
    (hasMemory
      ? '<span class="badge badge-memory">✓ MEMORY MATCH</span>'
      : '<span class="badge badge-general">ℹ NEW ERROR TYPE</span>') +
    `<span style="color:#8891a5;font-size:.75rem;margin-left:4px">${activeIncident.service} · ${activeIncident.error.slice(0, 50)}</span>`;

  // Memories
  const memories = data.memories || [];
  const expander = document.getElementById('memoriesExpander');
  if (memories.length > 0) {
    expander.style.display = 'block';
    document.getElementById('memCount').textContent = memories.length;
    const list = document.getElementById('memoriesList');
    list.innerHTML = memories.map((m, i) =>
      `<div class="memory-item"><b>Memory #${i + 1}</b><br>${escapeHtml(m)}</div>`
    ).join('');
  } else {
    expander.style.display = 'none';
  }

  // Agent response — convert markdown-like headings
  const html = markdownToHtml(data.response || 'No response.');
  document.getElementById('agentResponse').innerHTML = html;
  document.getElementById('resolveSection').style.display = 'block';
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
