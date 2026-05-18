// ── State ─────────────────────────────────────────
let active = null, history = [], totalQ = 0, totalCost = 0, memHits = 0, latencies = [];

// ── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  document.getElementById('alertForm').addEventListener('submit', handleAnalyze);
  document.getElementById('resolveForm').addEventListener('submit', handleResolve);
  document.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); toggleCmd(); }
    if (e.key === 'Escape') { closeCmd(); closeResolve(); }
  });
});

async function loadStats() {
  try {
    const r = await fetch('/api/stats');
    const d = await r.json();
    const c = d.memory_count || d.total_memories || '—';
    document.getElementById('memStat').textContent = c;
  } catch { document.getElementById('memStat').textContent = '—'; }
}

// ── Analyze ───────────────────────────────────────
async function handleAnalyze(e) {
  e.preventDefault();
  const service = document.getElementById('service').value;
  const error = document.getElementById('error').value.trim();
  const sev = document.querySelector('input[name="sev"]:checked').value;
  if (!error) return toast('Enter an error message', 'error');

  showLoading(true);
  try {
    const r = await fetch('/api/analyze', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_name: service, error_message: error, severity: sev }),
    });
    const data = await r.json();
    active = { service, error, severity: sev };
    totalQ++; totalCost += data.total_cost || 0;
    latencies.push(data.latency_ms || 0);
    if ((data.memory_count || 0) > 0) memHits++;

    history.push({
      time: new Date().toLocaleTimeString('en-US', { hour12: false }),
      service, error: error.slice(0, 80), severity: sev,
      hadMemory: (data.memory_count || 0) > 0,
      model: data.model_used || '—', cost: data.total_cost || 0,
      latency: data.latency_ms || 0,
    });

    showLoading(false);
    renderResponse(data, sev);
    renderAudit(data, sev);
    renderTimeline();
    updateAnalytics();
    toast('Analysis complete', 'success');
  } catch (err) {
    showLoading(false); toast('Error: ' + err.message, 'error');
  }
}

// ── Render Response ───────────────────────────────
function renderResponse(data, sev) {
  const el = document.getElementById('responseContent');
  el.style.display = 'block';
  document.getElementById('emptyState').style.display = 'none';

  const hasMem = (data.memory_count || 0) > 0;
  document.getElementById('responseBadges').innerHTML =
    `<span class="badge badge-sev-${sev}">${sev}</span>` +
    (hasMem ? '<span class="badge badge-memory">✓ Memory Match</span>' : '<span class="badge badge-new">New Error</span>');

  const memories = data.memories || [];
  const ms = document.getElementById('memorySection');
  if (memories.length > 0) {
    ms.style.display = 'block';
    document.getElementById('memTitle').textContent = `${memories.length} memories recalled`;
    document.getElementById('memoryCards').innerHTML = memories.map((m, i) =>
      `<div class="mem-card"><b>Memory #${i + 1}</b><br>${esc(m)}</div>`).join('');
  } else { ms.style.display = 'none'; }

  const html = md(data.response || '⚠️ No response.');
  document.getElementById('aiResponse').innerHTML = html;
}

// ── Render Audit ──────────────────────────────────
function renderAudit(data, sev) {
  document.getElementById('auditEmpty').style.display = 'none';
  document.getElementById('auditContent').style.display = 'block';

  const model = data.model_used || '—';
  const isDraft = model.includes('8b');
  const rb = document.getElementById('routeBadge');
  rb.className = 'route-badge ' + (isDraft ? 'route-drafter' : 'route-verifier');
  rb.textContent = isDraft ? '⚡ DRAFTER' : '🔬 VERIFIER';

  const cost = data.total_cost || 0, lat = data.latency_ms || 0;
  const budget = data.severity_budget || 0.25, savings = data.cost_saved_percentage || 0;

  document.getElementById('auditGrid').innerHTML = `
    <div class="a-card full"><div class="a-label">Model</div><div class="a-value a-blue" style="font-size:.78rem;word-break:break-all">${esc(model)}</div></div>
    <div class="a-card"><div class="a-label">Cost</div><div class="a-value a-green">$${cost.toFixed(6)}</div></div>
    <div class="a-card"><div class="a-label">Latency</div><div class="a-value a-orange">${lat.toFixed(0)}ms</div></div>
    <div class="a-card"><div class="a-label">Budget</div><div class="a-value">$${budget.toFixed(2)}</div></div>
    <div class="a-card"><div class="a-label">Savings</div><div class="a-value ${savings > 0 ? 'a-green' : ''}">${savings.toFixed(1)}%</div></div>`;

  const rationales = { P1: '🔴 Critical → Verifier model ($0.50 budget)', P2: '🟡 High → Drafter first ($0.25 budget)', P3: '🟢 Medium → Fast drafter ($0.10 budget)' };
  document.getElementById('auditRationale').textContent = rationales[sev] || '';

  const wrap = document.getElementById('costBarWrap');
  wrap.style.display = 'block';
  const pct = Math.min((cost / budget) * 100, 100);
  document.getElementById('costFill').style.width = pct + '%';
  document.getElementById('costUsed').textContent = '$' + cost.toFixed(6);
  document.getElementById('costBudget').textContent = '$' + budget.toFixed(2);

  const trace = data.trace || [], summary = data.summary || {};
  if (trace.length || Object.keys(summary).length) {
    document.getElementById('traceToggle').style.display = 'flex';
    document.getElementById('traceBlock').textContent = JSON.stringify({ trace, summary }, null, 2);
  }
}

// ── Resolve ───────────────────────────────────────
function openResolve() { if (active) document.getElementById('resolveModal').style.display = 'flex'; }
function closeResolve() { document.getElementById('resolveModal').style.display = 'none'; }

async function handleResolve(e) {
  e.preventDefault();
  if (!active) return;
  const rc = document.getElementById('rootCause').value.trim();
  const fix = document.getElementById('fixApplied').value.trim();
  const by = document.getElementById('resolvedBy').value.trim();
  if (!rc || !fix || !by) return toast('Fill in all fields', 'error');

  const st = document.getElementById('resolveStatus');
  st.innerHTML = '<span style="color:var(--t3)">Writing to Hindsight…</span>';
  try {
    const r = await fetch('/api/resolve', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service_name: active.service, error_message: active.error, severity: active.severity, root_cause: rc, fix_applied: fix, resolved_by: by }),
    });
    const d = await r.json();
    if (d.success) {
      toast('✅ Resolution saved to memory!', 'success');
      closeResolve(); document.getElementById('resolveForm').reset(); loadStats();
    } else { st.innerHTML = '<span style="color:var(--red)">Failed</span>'; }
  } catch (err) { st.innerHTML = `<span style="color:var(--red)">${err.message}</span>`; }
}

// ── Timeline ──────────────────────────────────────
function renderTimeline() {
  const el = document.getElementById('timeline');
  if (!history.length) return;
  el.innerHTML = history.slice().reverse().map((h, i) => {
    const isLast = i === history.length - 1;
    return `<div class="tl-item">
      <div class="tl-line"><div class="tl-dot ${h.severity.toLowerCase()}"></div>${isLast ? '' : '<div class="tl-connector"></div>'}</div>
      <div class="tl-body">
        <div class="tl-title">${esc(h.error)}</div>
        <div class="tl-meta">
          <span>${h.time}</span><span>${h.service}</span><span class="badge badge-sev-${h.severity}" style="padding:1px 6px">${h.severity}</span>
          <span>${h.hadMemory ? '🟢 Memory' : '🔴 New'}</span>
          <span>$${h.cost.toFixed(6)}</span>
        </div>
      </div></div>`;
  }).join('');
}

// ── Analytics ─────────────────────────────────────
function updateAnalytics() {
  document.getElementById('aQueries').textContent = totalQ;
  document.getElementById('aCost').textContent = '$' + totalCost.toFixed(5);
  document.getElementById('aHitRate').textContent = totalQ ? Math.round(memHits / totalQ * 100) + '%' : '0%';
  document.getElementById('aLatency').textContent = latencies.length ? Math.round(latencies.reduce((a, b) => a + b) / latencies.length) + 'ms' : '0ms';
  const verifierCost = 0.00059, drafterCost = 0.00005;
  const saved = totalQ * (verifierCost - drafterCost) * 500;
  document.getElementById('aSaved').textContent = '$' + saved.toFixed(4);
  const drafterCount = history.filter(h => h.model.includes('8b')).length;
  document.getElementById('aDrafter').textContent = totalQ ? Math.round(drafterCount / totalQ * 100) + '%' : '0%';
}

// ── Views ─────────────────────────────────────────
function switchView(v) {
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.getElementById('view-' + v).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === v));
}

// ── Command Palette ───────────────────────────────
function toggleCmd() { const o = document.getElementById('cmdOverlay'); o.style.display = o.style.display === 'none' ? 'flex' : 'none'; if (o.style.display === 'flex') document.getElementById('cmdInput').focus(); }
function closeCmd() { document.getElementById('cmdOverlay').style.display = 'none'; }
function cmdAction(a) { closeCmd(); if (a === 'history') switchView('history'); else if (a === 'analytics') switchView('analytics'); else switchView('dashboard'); }
function cmdService(s) { closeCmd(); switchView('dashboard'); document.getElementById('service').value = s; }
document.getElementById('cmdOverlay')?.addEventListener('click', e => { if (e.target === e.currentTarget) closeCmd(); });

// ── Loading ───────────────────────────────────────
function showLoading(show) {
  document.getElementById('loadingState').style.display = show ? 'block' : 'none';
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('responseContent').style.display = show ? 'none' : (active ? 'block' : 'none');
  document.getElementById('analyzeBtn').disabled = show;
  if (show) {
    const steps = ['step1', 'step2', 'step3'];
    steps.forEach(s => { document.getElementById(s).className = 'step'; });
    document.getElementById('step1').classList.add('active');
    setTimeout(() => { document.getElementById('step1').classList.replace('active', 'done'); document.getElementById('step2').classList.add('active'); }, 800);
    setTimeout(() => { document.getElementById('step2').classList.replace('active', 'done'); document.getElementById('step3').classList.add('active'); }, 1800);
  }
}

// ── Toast ─────────────────────────────────────────
function toast(msg, type = 'success') {
  const c = document.getElementById('toasts');
  const t = document.createElement('div');
  t.className = 'toast ' + type; t.textContent = msg;
  c.appendChild(t); setTimeout(() => t.remove(), 3500);
}

// ── Helpers ───────────────────────────────────────
function toggleEl(id) { const el = document.getElementById(id); el.style.display = el.style.display === 'none' ? 'block' : 'none'; }
function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
function md(t) {
  return t.replace(/### (.*)/g, '<h3>$1</h3>').replace(/## (.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/^\- (.*)/gm, '<li>$1</li>').replace(/^\d+\. (.*)/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>').replace(/<\/ul>\s*<ul>/g, '')
    .replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
}
