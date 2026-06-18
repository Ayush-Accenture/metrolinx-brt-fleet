// UI logic for the PDS Agentic Operations dashboard.
// Reads STEPS / DETAILS / PANELS from data.js.

let panelOpen = false;
let activeGate = 'HITL-2';

// Snapshot of the original "Completed" detail so a reset can restore it
// (approveH4 overwrites DETAILS[11] with the finished-run version).
const INITIAL_DETAIL_11 = DETAILS[11];

function buildPipeline() {
  const c = document.getElementById('pipeline');
  c.innerHTML = '';
  STEPS.forEach((s, i) => {
    const wrap = document.createElement('div');
    wrap.className = 'step-wrap';
    const step = document.createElement('div');
    step.className = `step ${s.state}`;
    step.id = `step-${i}`;
    step.onclick = () => showDetail(i);
    step.innerHTML = `
      <div class="step-icon">${s.icon}${s.isHITL ? '<span class="hitl-badge">HITL</span>' : ''}</div>
      <div class="step-label">${s.label}</div>
      <div class="step-sublabel" id="sub-${i}">${s.sub}</div>`;
    wrap.appendChild(step);
    if (i < STEPS.length - 1) {
      const conn = document.createElement('div');
      conn.className = `connector${s.state === 'done' ? ' done' : ''}`;
      conn.id = `conn-${i}`;
      wrap.appendChild(conn);
    }
    c.appendChild(wrap);
    setTimeout(() => step.classList.add('visible'), 110 * i);
  });
  updateProgress();
}

function updateProgress() {
  const total = STEPS.length;
  const done = document.querySelectorAll('.pipeline .step.done').length;
  const fill = document.getElementById('progressFill');
  const count = document.getElementById('progressCount');
  if (fill) fill.style.width = Math.round((done / total) * 100) + '%';
  if (count) count.textContent = `${done} / ${total}`;
}

function showDetail(i) {
  const d = DETAILS[i];
  const card = document.getElementById('detailCard');
  card.className = `detail-card show${d.isHITL ? ' hitl-card' : ''}`;
  card.innerHTML = `<h3>${d.title}</h3><div class="stage-tag">${d.stage}</div>${d.html}`;
}

function togglePanel() {
  panelOpen = !panelOpen;
  const panel = document.getElementById('hitlPanel');
  const overlay = document.getElementById('panelOverlay');
  const notifBtn = document.getElementById('notifBtn');

  panel.classList.toggle('open', panelOpen);
  panel.setAttribute('aria-hidden', String(!panelOpen));
  document.getElementById('mainWrap').classList.toggle('panel-open', panelOpen);
  if (notifBtn) notifBtn.setAttribute('aria-expanded', String(panelOpen));

  if (panelOpen) {
    overlay.hidden = false;
    requestAnimationFrame(() => overlay.classList.add('show'));
  } else {
    overlay.classList.remove('show');
    setTimeout(() => { overlay.hidden = true; }, 350);
  }
}

function renderPanel(key) {
  const p = PANELS[key];
  document.getElementById('panelGateBadge').textContent = p.badge;
  document.getElementById('panelTitle').textContent = p.title;
  document.getElementById('panelSubtitle').textContent = p.sub;
  document.getElementById('panelBody').innerHTML = p.body;
  document.getElementById('panelFooter').innerHTML = p.btns;
}

function setState(i, state) {
  const el = document.getElementById(`step-${i}`);
  if (el) el.className = `step ${state} visible`;
  updateProgress();
}
function setSub(i, txt) {
  const el = document.getElementById(`sub-${i}`);
  if (el) el.textContent = txt;
}
function connDone(i) {
  const el = document.getElementById(`conn-${i}`);
  if (el) el.classList.add('done');
}

function approveH2() {
  document.getElementById('primaryBtn').style.display = 'none';
  document.querySelector('#panelFooter .btn-danger').style.display = 'none';
  document.getElementById('doneMsg').style.display = 'block';

  setTimeout(() => {
    togglePanel();
    document.getElementById('hitlBanner').style.display = 'none';
    document.getElementById('notifBadge').style.display = 'none';
    document.getElementById('runStatus').textContent = 'Executing Moves';
    document.getElementById('runStatus').style.color = '#f39c12';

    setState(5, 'done'); connDone(5);
    setState(6, 'running'); setSub(6, 'In progress...');

    setTimeout(() => {
      setState(6, 'done'); setSub(6, '12:33 AM'); connDone(6);
      setState(7, 'running'); setSub(7, 'Polling SOTI...');
      document.getElementById('runStatus').textContent = 'Reconciling...';

      setTimeout(() => {
        setState(7, 'done'); setSub(7, '12:35 AM'); connDone(7);
        setState(8, 'hitl-active'); activeGate = 'HITL-3';
        renderPanel('HITL-3');
        document.getElementById('runStatus').textContent = 'Awaiting HITL-3 Validation';
        document.getElementById('runStatus').style.color = '#d68910';
        document.getElementById('hitlBanner').style.display = 'flex';
        document.getElementById('bannerTitle').textContent = 'Action Required — HITL-3: Post-Move Validation';
        document.getElementById('bannerMeta').textContent = 'Reconciliation complete. Review device move results before SR is drafted.';
        document.getElementById('notifBadge').style.display = 'flex';
        setTimeout(() => togglePanel(), 600);
      }, 2200);
    }, 2800);
  }, 1200);
}

function approveH3() {
  document.getElementById('primaryBtn').style.display = 'none';
  document.querySelector('#panelFooter .btn-outline').style.display = 'none';
  document.getElementById('doneMsg').style.display = 'block';

  setTimeout(() => {
    togglePanel();
    document.getElementById('hitlBanner').style.display = 'none';
    document.getElementById('notifBadge').style.display = 'none';

    setState(8, 'done'); connDone(8);
    setState(9, 'running'); setSub(9, 'LLM drafting...');
    document.getElementById('runStatus').textContent = 'Drafting SR...';
    document.getElementById('runStatus').style.color = '#8e44ad';

    setTimeout(() => {
      setState(9, 'done'); setSub(9, '12:38 AM'); connDone(9);
      setState(10, 'hitl-active'); activeGate = 'HITL-4';
      renderPanel('HITL-4');
      document.getElementById('runStatus').textContent = 'Awaiting HITL-4 SR Closure';
      document.getElementById('runStatus').style.color = '#d68910';
      document.getElementById('hitlBanner').style.display = 'flex';
      document.getElementById('bannerTitle').textContent = 'Action Required — HITL-4: SR Closure Review';
      document.getElementById('bannerMeta').textContent = 'SR draft is ready. Review and approve to close the ServiceNow ticket.';
      document.getElementById('notifBadge').style.display = 'flex';
      setTimeout(() => togglePanel(), 600);
    }, 2500);
  }, 1200);
}

function approveH4() {
  document.getElementById('primaryBtn').style.display = 'none';
  document.querySelector('#panelFooter .btn-outline').style.display = 'none';
  document.getElementById('doneMsg').style.display = 'block';

  setTimeout(() => {
    togglePanel();
    document.getElementById('hitlBanner').style.display = 'none';
    document.getElementById('notifBadge').style.display = 'none';

    setState(10, 'done'); connDone(10);
    setState(11, 'done'); setSub(11, '12:40 AM');
    document.getElementById('runStatus').textContent = 'Completed ✅';
    document.getElementById('runStatus').style.color = '#27ae60';

    DETAILS[11] = { title:'✅ Completed', stage:'COMPLETE', isHITL:false, html:`
      <div class="detail-grid">
        <div class="detail-item"><label>Status</label><p><span class="badge badge-green">COMPLETED</span></p></div>
        <div class="detail-item"><label>Completed At</label><p>12:40 AM · Jun 17, 2026</p></div>
        <div class="detail-item"><label>Moved to LTM</label><p>4 devices</p></div>
        <div class="detail-item"><label>Moved to Prod</label><p>3 devices</p></div>
        <div class="detail-item"><label>Failures</label><p>0</p></div>
        <div class="detail-item"><label>SR</label><p>Closed in ServiceNow</p></div>
      </div>
      <table class="detail-table">
        <tr><th>Device</th><th>Action</th><th>Result</th></tr>
        <tr><td>BRT-BFTP-1003</td><td>→ LTM</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>BRT-DCU-1003</td> <td>→ LTM</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>BRT-BFTP-1004</td><td>→ LTM</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>BRT-DCU-1004</td> <td>→ LTM</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>LTM-BRT-BFTP-9001</td><td>→ Prod</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>LTM-BRT-BFTP-9002</td><td>→ Prod</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
        <tr><td>LTM-BRT-DCU-9001</td> <td>→ Prod</td><td><span class="badge badge-green">✅ Moved</span></td></tr>
      </table>`};
    showDetail(11);
  }, 1200);
}

function scrollPipeline(dir) {
  const el = document.getElementById('pipelineScroll');
  el.scrollBy({ left: dir * Math.max(300, el.clientWidth * 0.7), behavior: 'smooth' });
  setTimeout(updateScrollBtns, 400);
}

function updateScrollBtns() {
  const el = document.getElementById('pipelineScroll');
  const overflow = el.scrollWidth - el.clientWidth;
  const left = document.getElementById('scrollLeft');
  const right = document.getElementById('scrollRight');
  // If there's nothing to scroll, hide the arrows entirely.
  if (overflow <= 2) {
    left.style.display = 'none';
    right.style.display = 'none';
    return;
  }
  left.style.display = right.style.display = 'flex';
  left.disabled = el.scrollLeft <= 2;
  right.disabled = el.scrollLeft >= overflow - 2;
}

function rejectRun() {
  togglePanel();
  showToast('Run rejected. The orchestrator has been notified.', 'danger');
}

/* ---------------- Reset / replay the simulation ---------------- */
function resetSimulation() {
  if (panelOpen) togglePanel();          // close the slide-over if it's open
  activeGate = 'HITL-2';
  DETAILS[11] = INITIAL_DETAIL_11;       // restore original "Completed" card

  buildPipeline();                        // rebuilds all stages from the (unmutated) STEPS
  renderPanel('HITL-2');

  // Restore banner + notification badge
  const banner = document.getElementById('hitlBanner');
  banner.style.display = 'flex';
  document.getElementById('bannerTitle').textContent = 'Action Required — HITL-2: Pre-Move Approval';
  document.getElementById('bannerMeta').textContent = 'Fleet Movement Plan for BRT Brampton (Jun 17, 2026) is awaiting your review before execution begins.';
  document.getElementById('notifBadge').style.display = 'flex';

  // Restore run status (clear inline color so the amber class shows again)
  const status = document.getElementById('runStatus');
  status.textContent = 'Awaiting HITL-2 Approval';
  status.style.color = '';

  // Reset the detail card to the active HITL-2 stage
  document.getElementById('detailCard').className = 'detail-card';
  setTimeout(() => showDetail(5), 400);

  setTimeout(updateScrollBtns, 200);
  showToast('Simulation reset to the start.', 'info');
}

/* ---------------- Toasts ---------------- */
function showToast(message, type = 'info') {
  const wrap = document.getElementById('toastWrap');
  if (!wrap) return;
  const icons = { info: 'ℹ️', success: '✅', warn: '⚠️', danger: '❌' };
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span class="toast-icon">${icons[type] || icons.info}</span><span>${message}</span>`;
  wrap.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add('show'));
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
  }, 3600);
}

/* ---------------- Theme ---------------- */
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const btn = document.getElementById('themeBtn');
  if (btn) {
    btn.textContent = theme === 'dark' ? '☀️' : '🌙';
    btn.setAttribute('title', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
  }
  try { localStorage.setItem('pds-theme', theme); } catch (e) { /* ignore */ }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  applyTheme(current === 'dark' ? 'light' : 'dark');
}

function initTheme() {
  let theme = 'light';
  try {
    const saved = localStorage.getItem('pds-theme');
    if (saved) theme = saved;
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) theme = 'dark';
  } catch (e) { /* ignore */ }
  applyTheme(theme);
}

window.addEventListener('load', () => {
  initTheme();
  buildPipeline();
  renderPanel('HITL-2');
  setTimeout(() => showDetail(5), 900);
  const scroll = document.getElementById('pipelineScroll');
  scroll.addEventListener('scroll', updateScrollBtns);
  window.addEventListener('resize', updateScrollBtns);
  setTimeout(updateScrollBtns, 300);

  // Close the slide-over panel with the Escape key.
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && panelOpen) togglePanel();
  });
});
