// Pipeline stage definitions, per-stage detail cards, and HITL panel content.
// Pure data — no DOM logic here (see app.js).

const STEPS = [
  { icon:'📧', label:'Email Received',    sub:'12:01 AM', state:'done',         stage:'RECEIVE_DVA',      isHITL:false },
  { icon:'🔗', label:'File Bound',        sub:'12:02 AM', state:'done',         stage:'BIND_INTAKE',      isHITL:false },
  { icon:'🔍', label:'Schema Check',      sub:'12:03 AM', state:'done',         stage:'STRUCTURAL_CHECK', isHITL:false },
  { icon:'📡', label:'SOTI Snapshot',     sub:'12:15 AM', state:'done',         stage:'SOTI_SNAPSHOT',    isHITL:false },
  { icon:'📋', label:'Plan Generated',    sub:'12:30 AM', state:'done',         stage:'PLAN_MOVES',       isHITL:false },
  { icon:'👤', label:'Pre-Move Approval', sub:'HITL-2',   state:'hitl-active',  stage:'RAISE_HITL2',      isHITL:true  },
  { icon:'⚙️', label:'Executing Moves',   sub:'Pending',  state:'pending',      stage:'MOVE_DEVICES',     isHITL:false },
  { icon:'🔄', label:'Reconciliation',    sub:'Pending',  state:'pending',      stage:'VERIFY_MOVES',     isHITL:false },
  { icon:'👤', label:'Post-Move Review',  sub:'HITL-3',   state:'hitl-pending', stage:'RAISE_HITL3',      isHITL:true  },
  { icon:'📝', label:'SR Draft',          sub:'Pending',  state:'pending',      stage:'DRAFT_SR',         isHITL:false },
  { icon:'👤', label:'SR Closure',        sub:'HITL-4',   state:'hitl-pending', stage:'RAISE_HITL4',      isHITL:true  },
  { icon:'✅', label:'Completed',         sub:'Pending',  state:'pending',      stage:'COMPLETE',         isHITL:false },
];

const DETAILS = {
  0: { title:'📧 Email Received', stage:'RECEIVE_DVA', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>From</label><p>PRESTODeviceAvailability@brampton.ca</p></div>
      <div class="detail-item"><label>Subject</label><p>[External] Brampton DVA | Tue Jun 17, 2026</p></div>
      <div class="detail-item"><label>Received</label><p>Jun 17, 2026 · 12:01 AM UTC</p></div>
      <div class="detail-item"><label>Attachment</label><p>Brampton's Device Vehicle Allocation File.xlsx</p></div>
      <div class="detail-item"><label>File Size</label><p>6,117 bytes</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-green">RECEIVED</span></p></div>
    </div>`},
  1: { title:'🔗 File Bound', stage:'BIND_INTAKE', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Message ID</label><p>intake_BRT_2026-06-17</p></div>
      <div class="detail-item"><label>Blob Path</label><p style="font-size:11px;word-break:break-all">fmi/raw/Brampton_DVA_2026-06-17.xlsx</p></div>
      <div class="detail-item"><label>Collection</label><p>fmi-db / intake</p></div>
      <div class="detail-item"><label>HITL-1 Triggered</label><p>No — file on time</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-green">BOUND</span></p></div>
    </div>`},
  2: { title:'🔍 Schema Check', stage:'STRUCTURAL_CHECK', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Sheet</label><p>Brampton's Device Vehicle Alloc</p></div>
      <div class="detail-item"><label>Bus # Column</label><p>✅ Found (row 2)</p></div>
      <div class="detail-item"><label>Vehicle Status Column</label><p>✅ Found</p></div>
      <div class="detail-item"><label>Total Rows</label><p>22 buses</p></div>
      <div class="detail-item"><label>HITL-Schema Triggered</label><p>No — schema valid</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-green">PASSED</span></p></div>
    </div>`},
  3: { title:'📡 SOTI Snapshot', stage:'SOTI_SNAPSHOT', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Org ID</label><p>3 — BRT Brampton</p></div>
      <div class="detail-item"><label>BFTP in Production</label><p>18 devices</p></div>
      <div class="detail-item"><label>BFTP in LTM</label><p>4 devices</p></div>
      <div class="detail-item"><label>DCU in Production</label><p>18 devices</p></div>
      <div class="detail-item"><label>DCU in LTM</label><p>3 devices</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-green">SNAPSHOT READY</span></p></div>
    </div>`},
  4: { title:'📋 Plan Generated', stage:'PLAN_MOVES', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Total Buses</label><p>22</p></div>
      <div class="detail-item"><label>Off-Site (LTM)</label><p>3 buses</p></div>
      <div class="detail-item"><label>Devices → LTM</label><p>4</p></div>
      <div class="detail-item"><label>Devices → Production</label><p>3</p></div>
      <div class="detail-item"><label>Already Correct</label><p>7</p></div>
      <div class="detail-item"><label>Unidentified</label><p>1</p></div>
    </div>
    <table class="detail-table">
      <tr><th>Device</th><th>Type</th><th>Action</th><th>Bus</th></tr>
      <tr><td>BRT-BFTP-1003</td><td>BFTP</td><td><span class="badge badge-amber">→ LTM</span></td><td>1003</td></tr>
      <tr><td>BRT-DCU-1003</td><td>DCU</td><td><span class="badge badge-amber">→ LTM</span></td><td>1003</td></tr>
      <tr><td>BRT-BFTP-1004</td><td>BFTP</td><td><span class="badge badge-amber">→ LTM</span></td><td>1004</td></tr>
      <tr><td>BRT-DCU-1004</td><td>DCU</td><td><span class="badge badge-amber">→ LTM</span></td><td>1004</td></tr>
      <tr><td>LTM-BRT-BFTP-9001</td><td>BFTP</td><td><span class="badge badge-green">→ Prod</span></td><td>—</td></tr>
      <tr><td>LTM-BRT-BFTP-9002</td><td>BFTP</td><td><span class="badge badge-green">→ Prod</span></td><td>—</td></tr>
      <tr><td>LTM-BRT-DCU-9001</td><td>DCU</td><td><span class="badge badge-green">→ Prod</span></td><td>—</td></tr>
    </table>`},
  5: { title:'👤 Pre-Move Approval', stage:'RAISE_HITL2', isHITL:true, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Gate</label><p>HITL-2 — Pre-Move Approval</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-amber">AWAITING DECISION</span></p></div>
      <div class="detail-item"><label>Waiting Since</label><p>12:31 AM</p></div>
      <div class="detail-item"><label>Options</label><p>Approve All · Approve Subset · Reject</p></div>
    </div>`},
  6: { title:'⚙️ Executing Moves', stage:'MOVE_DEVICES', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">NOT STARTED</span></p></div>
      <div class="detail-item"><label>Note</label><p>Waiting for HITL-2 approval</p></div>
    </div>`},
  7: { title:'🔄 Reconciliation', stage:'VERIFY_MOVES', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">NOT STARTED</span></p></div>
      <div class="detail-item"><label>Note</label><p>Polls SOTI to verify actual device locations after moves complete</p></div>
    </div>`},
  8: { title:'👤 Post-Move Review', stage:'RAISE_HITL3', isHITL:true, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Gate</label><p>HITL-3 — Post-Move Validation</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">WAITING</span></p></div>
      <div class="detail-item"><label>Options</label><p>Confirm · Recheck SOTI · Flag Exception · Correct Inline</p></div>
    </div>`},
  9: { title:'📝 SR Draft', stage:'DRAFT_SR', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">NOT STARTED</span></p></div>
      <div class="detail-item"><label>Note</label><p>LLM generates ServiceNow SR notes and stakeholder summary email</p></div>
    </div>`},
  10:{ title:'👤 SR Closure', stage:'RAISE_HITL4', isHITL:true, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Gate</label><p>HITL-4 — SR Closure Review</p></div>
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">WAITING</span></p></div>
      <div class="detail-item"><label>Options</label><p>Approve & Close SR · Edit Details · Keep Open</p></div>
    </div>`},
  11:{ title:'✅ Completed', stage:'COMPLETE', isHITL:false, html:`
    <div class="detail-grid">
      <div class="detail-item"><label>Status</label><p><span class="badge badge-gray">NOT STARTED</span></p></div>
    </div>`},
};

const PANELS = {
  'HITL-2': {
    badge:'HITL-2', title:'Pre-Move Approval Required',
    sub:'run_BRT_2026-06-17 · Jun 17, 2026 · BRT Brampton',
    body:`
      <div class="panel-section">
        <h4>Summary</h4>
        <div class="summary-grid">
          <div class="summary-stat"><div class="val">4</div><div class="lbl">Devices → LTM</div></div>
          <div class="summary-stat"><div class="val">3</div><div class="lbl">Devices → Prod</div></div>
          <div class="summary-stat"><div class="val">3</div><div class="lbl">Buses Off-Site</div></div>
          <div class="summary-stat"><div class="val">1</div><div class="lbl">Unidentified</div></div>
        </div>
      </div>
      <div class="panel-section">
        <h4>Moving to LTM</h4>
        <ul class="device-list">
          <li><span class="dev-tag">BFTP</span> BRT-BFTP-1003 <span class="dev-bus">Bus 1003</span></li>
          <li><span class="dev-tag">DCU</span>  BRT-DCU-1003  <span class="dev-bus">Bus 1003</span></li>
          <li><span class="dev-tag">BFTP</span> BRT-BFTP-1004 <span class="dev-bus">Bus 1004</span></li>
          <li><span class="dev-tag">DCU</span>  BRT-DCU-1004  <span class="dev-bus">Bus 1004</span></li>
        </ul>
      </div>
      <div class="panel-section">
        <h4>Returning to Production</h4>
        <ul class="device-list">
          <li><span class="dev-tag">BFTP</span> LTM-BRT-BFTP-9001 <span class="dev-bus">Returning</span></li>
          <li><span class="dev-tag">BFTP</span> LTM-BRT-BFTP-9002 <span class="dev-bus">Returning</span></li>
          <li><span class="dev-tag">DCU</span>  LTM-BRT-DCU-9001  <span class="dev-bus">Returning</span></li>
        </ul>
      </div>
      <div class="panel-section">
        <h4>Unidentified — will be skipped</h4>
        <ul class="device-list">
          <li>🔍 Bus 1005 — BFTP not found in SOTI <span class="dev-bus">Skipped</span></li>
        </ul>
      </div>`,
    btns:`
      <div class="done-msg" id="doneMsg">✅ Approved! Execution starting...</div>
      <button class="btn-primary" id="primaryBtn" onclick="approveH2()">✅ Approve All & Execute</button>
      <button class="btn-danger" onclick="rejectRun()">❌ Reject</button>`,
  },
  'HITL-3': {
    badge:'HITL-3', title:'Post-Move Validation',
    sub:'run_BRT_2026-06-17 · Reconciliation complete',
    body:`
      <div class="panel-section">
        <h4>Reconciliation Summary</h4>
        <div class="summary-grid">
          <div class="summary-stat"><div class="val" style="color:#27ae60">7</div><div class="lbl">Confirmed</div></div>
          <div class="summary-stat"><div class="val" style="color:#e94560">0</div><div class="lbl">Failures</div></div>
          <div class="summary-stat"><div class="val" style="color:#f39c12">1</div><div class="lbl">Skipped</div></div>
          <div class="summary-stat"><div class="val" style="color:#27ae60">100%</div><div class="lbl">Success</div></div>
        </div>
      </div>
      <div class="panel-section">
        <h4>Verified Moves</h4>
        <div class="recon-row recon-ok"><span>BRT-BFTP-1003</span><span style="margin-left:auto;font-size:11px;color:#27ae60">→ LTM ✅</span></div>
        <div class="recon-row recon-ok"><span>BRT-DCU-1003</span> <span style="margin-left:auto;font-size:11px;color:#27ae60">→ LTM ✅</span></div>
        <div class="recon-row recon-ok"><span>BRT-BFTP-1004</span><span style="margin-left:auto;font-size:11px;color:#27ae60">→ LTM ✅</span></div>
        <div class="recon-row recon-ok"><span>BRT-DCU-1004</span> <span style="margin-left:auto;font-size:11px;color:#27ae60">→ LTM ✅</span></div>
        <div class="recon-row recon-ok"><span>LTM-BRT-BFTP-9001</span><span style="margin-left:auto;font-size:11px;color:#27ae60">→ Prod ✅</span></div>
        <div class="recon-row recon-ok"><span>LTM-BRT-BFTP-9002</span><span style="margin-left:auto;font-size:11px;color:#27ae60">→ Prod ✅</span></div>
        <div class="recon-row recon-ok"><span>LTM-BRT-DCU-9001</span> <span style="margin-left:auto;font-size:11px;color:#27ae60">→ Prod ✅</span></div>
      </div>
      <div class="panel-section">
        <h4>Skipped</h4>
        <div class="recon-row recon-warn"><span>Bus 1005 BFTP</span><span style="margin-left:auto;font-size:11px;color:#f39c12">Not found in SOTI</span></div>
      </div>`,
    btns:`
      <div class="done-msg" id="doneMsg">✅ Validated! Proceeding to SR Draft...</div>
      <button class="btn-primary" id="primaryBtn" onclick="approveH3()">✅ Confirm & Proceed</button>
      <button class="btn-outline" onclick="showToast('SOTI will be re-queried for the latest device locations.', 'info')">🔄 Recheck SOTI</button>`,
  },
  'HITL-4': {
    badge:'HITL-4', title:'SR Closure Review',
    sub:'run_BRT_2026-06-17 · ServiceNow SR ready',
    body:`
      <div class="panel-section">
        <h4>ServiceNow SR Draft</h4>
        <div class="sr-box">
          <div class="sr-field"><label>Short Description</label>BRT Fleet Device Reallocation — Jun 17, 2026</div>
          <div class="sr-field"><label>Category</label>Fleet Management / SOTI MobiControl</div>
          <div class="sr-field"><label>Narrative</label>Nightly DVA processing completed for BRT Brampton (Jun 17, 2026). 4 devices moved to LTM (buses 1003, 1004 off-site) and 3 devices returned to Production. 1 unidentified device skipped (Bus 1005 BFTP not in SOTI). All 7 confirmed via reconciliation. No failures.</div>
        </div>
      </div>
      <div class="panel-section">
        <h4>Stakeholder Email Preview</h4>
        <div class="sr-box" style="border-left-color:#0f3460">
          <div class="sr-field"><label>To</label>Brampton Operations, Fleet Team</div>
          <div class="sr-field"><label>Subject</label>BRT Fleet DVA Processing Complete — Jun 17, 2026</div>
          <div class="sr-field"><label>Body</label>The nightly fleet device reallocation for Jun 17, 2026 has completed successfully. 7 devices moved (4 → LTM, 3 → Production). Full details in the attached workbook.</div>
        </div>
      </div>`,
    btns:`
      <div class="done-msg" id="doneMsg">✅ SR Closed! Run complete.</div>
      <button class="btn-primary" id="primaryBtn" onclick="approveH4()">✅ Approve & Close SR</button>
      <button class="btn-outline" onclick="showToast('SR kept open for further review.', 'warn')">📌 Keep SR Open</button>`,
  },
};
