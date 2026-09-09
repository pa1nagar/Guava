/**
 * app.js — Main application controller
 * Tab router, calculator handlers, DOM renderers
 * Imports from data.js, translator.js, charts.js
 */

import { setLanguage, init } from './translator.js';
import {
  NUTRIENTS_DATA, CALENDAR_DATA, IPM_DATA,
  ORCHARD, OPEX_BASE, IRRIGATION_STAGES,
  PROCUREMENT_BASE, DIAGNOSTIC_PARAMS
} from './data.js';

// Chart init functions — imported from charts.js
// These will be populated in Task 22; stub-safe imports for now
let initOverviewCharts = () => {};
let initMarketCharts   = () => {};
let initIrrigationChart = () => {};

// Lazy-load chart module (async to avoid blocking DOMContentLoaded on file://)
async function _loadCharts() {
  try {
    const charts = await import('./charts.js');
    initOverviewCharts  = charts.initOverviewCharts  || initOverviewCharts;
    initMarketCharts    = charts.initMarketCharts    || initMarketCharts;
    initIrrigationChart = charts.initIrrigationChart || initIrrigationChart;
  } catch (e) {
    console.warn('[App] charts.js not yet available:', e.message);
  }
}

// ─── Tab Router ──────────────────────────────────────────────────────────────

const chartsInitialized = {};

export function switchTab(tabId) {
  // Hide all panels, deactivate all nav buttons
  document.querySelectorAll('.tab-panel').forEach(p => { p.hidden = true; });
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  // Show target panel
  const panel = document.getElementById(`panel-${tabId}`);
  if (panel) panel.hidden = false;

  // Activate nav button
  const btn = document.getElementById(`btn-${tabId}`);
  if (btn) btn.classList.add('active');

  // Lazy-init content for this tab
  _lazyInitTab(tabId);
}

function _lazyInitTab(tabId) {
  if (chartsInitialized[tabId]) return;
  chartsInitialized[tabId] = true;

  switch (tabId) {
    case 'overview':
      initOverviewCharts();
      break;
    case 'market':
      initMarketCharts();
      runFinancialSim();
      break;
    case 'irrigation':
      initIrrigationChart();
      runIrrigationCalc();
      break;
    case 'nutrients':
      renderNutrientCards('all');
      break;
    case 'calendar':
      renderCalendarButtons();
      selectCalendarMonth(0);
      break;
    case 'health':
      renderHealthCards(IPM_DATA);
      break;
    case 'procurement':
      updateProcurement();
      break;
    case 'bagging':
      // Static content — no init needed
      break;
    case 'fertigation':
      // Static content — no init needed
      break;
    case 'warnings':
      // Static content — no init needed
      break;
    default:
      break;
  }
}

// ─── Language ────────────────────────────────────────────────────────────────

export function setLang(lang) {
  setLanguage(lang);
}

// ─── Global window wrappers (for inline onclick attributes) ──────────────────

window.switchTab        = switchTab;
window.setLang          = setLang;
window.filterNutrients  = filterNutrients;
window.filterHealthCards = filterHealthCards;
window.runFinancialSim  = runFinancialSim;
window.runIrrigationCalc = runIrrigationCalc;
window.updateProcurement = updateProcurement;
window.runDiagnosticLookup = runDiagnosticLookup;
window.selectCalendarMonth = selectCalendarMonth;

// ─── Nutrient Master Renderer ─────────────────────────────────────────────────

export function renderNutrientCards(category) {
  const grid = document.getElementById('nutrient-card-grid');
  if (!grid) return;

  const filtered = category === 'all'
    ? NUTRIENTS_DATA
    : NUTRIENTS_DATA.filter(n => n.category === category);

  grid.innerHTML = filtered.map(n => `
    <div class="nutrient-card" data-category="${n.category}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.75rem;">
        <div>
          <span style="font-size:1.5rem;font-weight:700;color:#1E3A2B;">${n.symbol}</span>
          <span style="font-size:1rem;font-weight:600;color:#2B2D42;margin-left:0.5rem;">${n.name}</span>
        </div>
        <span class="badge-${n.evidenceGrade}">${n.evidenceGrade === 'A' ? '🟢 A' : n.evidenceGrade === 'B' ? '🔵 B' : n.evidenceGrade === 'C' ? '🟡 C' : '🔴 E'}</span>
      </div>
      <p style="font-size:0.7rem;color:#888;font-style:italic;margin-bottom:0.5rem;">${n.imageLabel}</p>
      <table style="width:100%;font-size:0.8rem;border-collapse:collapse;">
        <tr><td style="padding:2px 4px;font-weight:600;color:#4A7C59;width:38%;">Role</td><td style="padding:2px 4px;">${n.role}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#4A7C59;">Crop Impact</td><td style="padding:2px 4px;">${n.impact}</td></tr>
        <tr><td style="padding:2px 4px;font-weight:600;color:#E07A5F;">Deficiency</td><td style="padding:2px 4px;">${n.deficiency}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#991b1b;">Excess</td><td style="padding:2px 4px;">${n.excess}</td></tr>
        <tr><td style="padding:2px 4px;font-weight:600;color:#1e40af;">Drip Dose</td><td style="padding:2px 4px;">${n.doseDrip}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#1e40af;">Foliar</td><td style="padding:2px 4px;">${n.doseFoliar}</td></tr>
        <tr><td style="padding:2px 4px;font-weight:600;color:#1e40af;">Soil</td><td style="padding:2px 4px;">${n.doseSoil}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#854d0e;">Vertisol</td><td style="padding:2px 4px;">${n.vertisol}</td></tr>
        <tr><td style="padding:2px 4px;font-weight:600;color:#991b1b;">Antagonism</td><td style="padding:2px 4px;">${n.antagonism}</td></tr>
      </table>
    </div>
  `).join('');
}

export function filterNutrients(cat) {
  // Update active state on filter buttons
  document.querySelectorAll('[data-filter-cat]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filterCat === cat);
  });
  renderNutrientCards(cat);
}

// ─── Farm Calendar Renderer ───────────────────────────────────────────────────

export function renderCalendarButtons() {
  const container = document.getElementById('calendar-month-buttons');
  if (!container) return;

  container.innerHTML = CALENDAR_DATA.map((entry, idx) => `
    <button
      onclick="selectCalendarMonth(${idx})"
      data-cal-idx="${idx}"
      style="padding:6px 14px;border-radius:8px;border:1px solid #4A7C59;background:${entry.droughtStop ? '#fee2e2' : '#f0fdf4'};color:${entry.droughtStop ? '#991b1b' : '#1E3A2B'};cursor:pointer;font-size:0.8rem;font-weight:600;transition:all 0.15s;">
      Month ${entry.month}${entry.droughtStop ? ' ⛔' : ''}
    </button>
  `).join('');
}

export function selectCalendarMonth(idx) {
  const entry = CALENDAR_DATA[idx];
  if (!entry) return;

  // Highlight active button
  document.querySelectorAll('[data-cal-idx]').forEach((btn, i) => {
    btn.style.outline = i === idx ? '2px solid #1E3A2B' : 'none';
  });

  const detail = document.getElementById('calendar-detail');
  if (!detail) return;

  const waterHtml = entry.droughtStop
    ? `<div style="background:#fee2e2;border:1px solid #f87171;border-radius:8px;padding:0.75rem;color:#991b1b;font-weight:700;font-size:0.9rem;">
         ⛔ SHUT OFF DRIP COMPLETELY — ${entry.waterFormula}
       </div>`
    : `<div><strong>${entry.waterLpd} L/plant/day</strong> &nbsp;<span style="color:#6b7280;font-size:0.8rem;">${entry.waterFormula}</span></div>`;

  detail.innerHTML = `
    <div style="background:#fff;border:1px solid #E2DCD5;border-radius:12px;padding:1.25rem;margin-top:1rem;">
      <h3 style="color:#1E3A2B;font-weight:700;margin-bottom:0.75rem;">${entry.title}</h3>
      <div style="display:grid;gap:0.75rem;">
        <div><span style="font-weight:600;color:#4A7C59;">Phenological Stage:</span> ${entry.pheno}</div>
        <div><span style="font-weight:600;color:#4A7C59;">Daily Water:</span> ${waterHtml}</div>
        <div><span style="font-weight:600;color:#4A7C59;">Fertigation:</span> ${entry.fert}</div>
        <div><span style="font-weight:600;color:#4A7C59;">Foliar Spray:</span> ${entry.foliar}</div>
        <div><span style="font-weight:600;color:#4A7C59;">Pruning / Training:</span> ${entry.pruning}</div>
        <div><span style="font-weight:600;color:#4A7C59;">IPM:</span> ${entry.ipm}</div>
      </div>
    </div>
  `;
}

// ─── Financial Simulator ──────────────────────────────────────────────────────

export function runFinancialSim() {
  const priceEl   = document.getElementById('sim-price');
  const yield2El  = document.getElementById('sim-yield2');
  const yield4El  = document.getElementById('sim-yield4');
  const bagEl     = document.getElementById('sim-bagcost');
  if (!priceEl || !yield2El || !yield4El || !bagEl) return;

  const price   = parseFloat(priceEl.value)  || 60;
  const yield2  = parseFloat(yield2El.value) || 18;
  const yield4  = parseFloat(yield4El.value) || 30;
  const bagCost = parseFloat(bagEl.value)    || 2.75;

  // Update display labels
  const priceDisplay = document.getElementById('sim-price-val');
  const yield2Display = document.getElementById('sim-yield2-val');
  const yield4Display = document.getElementById('sim-yield4-val');
  const bagDisplay = document.getElementById('sim-bagcost-val');
  if (priceDisplay)  priceDisplay.textContent = `₹${price}`;
  if (yield2Display) yield2Display.textContent = `${yield2} kg`;
  if (yield4Display) yield4Display.textContent = `${yield4} kg`;
  if (bagDisplay)    bagDisplay.textContent    = `₹${bagCost.toFixed(2)}`;

  const gross2  = ORCHARD.trees * yield2 * price;
  const fruits2 = (ORCHARD.trees * yield2) / ORCHARD.avgFruitWeightKg;
  const opex2   = OPEX_BASE.yr2 + (fruits2 * bagCost);
  const net2    = gross2 - opex2;

  const gross4  = ORCHARD.trees * yield4 * price;
  const fruits4 = (ORCHARD.trees * yield4) / ORCHARD.avgFruitWeightKg;
  const opex4   = OPEX_BASE.yr4 + (fruits4 * bagCost);
  const net4    = gross4 - opex4;

  _renderSimOutput('out-gross2', gross2, false);
  _renderSimOutput('out-net2',   net2,   true);
  _renderSimOutput('out-gross4', gross4, false);
  _renderSimOutput('out-net4',   net4,   true);
}

function _renderSimOutput(id, value, allowNegative) {
  const el = document.getElementById(id);
  if (!el) return;
  el.dataset.raw = value;
  if (allowNegative && value < 0) {
    el.style.color = '#dc2626';
    el.textContent = `−₹${Math.abs(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  } else {
    el.style.color = value >= 0 ? '#065f46' : '#dc2626';
    el.textContent = `₹${Math.abs(value).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
  }
}

// ─── Irrigation Calculator ────────────────────────────────────────────────────

export function runIrrigationCalc() {
  const stageEl = document.getElementById('irr-stage');
  const hwEl    = document.getElementById('irr-hardware');
  const etaEl   = document.getElementById('irr-efficiency');
  if (!stageEl || !hwEl || !etaEl) return;

  const stageId = stageEl.value;
  const stage   = IRRIGATION_STAGES.find(s => s.id === stageId) || IRRIGATION_STAGES[0];
  const eta     = Math.max(0.70, Math.min(1.0, parseFloat(etaEl.value) || 0.90));
  const hwVal   = hwEl.value || '2x4';

  // Parse hardware: "2x4" = 2 drippers × 4 L/h = 8 L/h total
  const [drippers, flowRate] = hwVal.split('x').map(Number);
  const flowPerHour = (drippers || 2) * (flowRate || 4);

  const volPerPlant    = (stage.et0 * stage.kc * stage.kr * ORCHARD.spacingM2) / eta;
  const orchardTotal   = volPerPlant * ORCHARD.trees;
  const runTimeHours   = volPerPlant / flowPerHour;

  const volEl   = document.getElementById('irr-vol');
  const rtEl    = document.getElementById('irr-runtime');
  const totEl   = document.getElementById('irr-orchard-total');

  if (volEl)  volEl.textContent  = `${volPerPlant.toFixed(2)} L/plant/day`;
  if (rtEl)   rtEl.textContent   = `${runTimeHours.toFixed(2)} hours/day`;
  if (totEl)  totEl.textContent  = `${(orchardTotal / 1000).toFixed(1)} kL/day (${orchardTotal.toFixed(0)} L/day)`;
}

// ─── Procurement Calculator ───────────────────────────────────────────────────

export function updateProcurement() {
  const slider = document.getElementById('proc-trees');
  if (!slider) return;

  const treeCount = parseInt(slider.value) || 2100;
  const display = document.getElementById('proc-trees-val');
  if (display) display.textContent = treeCount.toLocaleString('en-IN');

  _renderProcPanel('proc-fertilizers', PROCUREMENT_BASE.fertilizers, treeCount);
  _renderProcPanel('proc-bio',         PROCUREMENT_BASE.bio,         treeCount);
  _renderProcPanel('proc-hardware',    PROCUREMENT_BASE.hardware,    treeCount);
}

function _renderProcPanel(panelId, items, treeCount) {
  const el = document.getElementById(panelId);
  if (!el) return;

  el.innerHTML = `
    <table style="width:100%;font-size:0.8rem;border-collapse:collapse;">
      <thead>
        <tr style="background:#1E3A2B;color:#fff;">
          <th style="padding:6px 8px;text-align:left;">Item</th>
          <th style="padding:6px 8px;text-align:right;">Qty (${treeCount} trees)</th>
          <th style="padding:6px 8px;text-align:right;">Commercial Packs</th>
        </tr>
      </thead>
      <tbody>
        ${items.map((item, i) => {
          const scaledQty   = Math.ceil(item.qty2100 * treeCount / 2100);
          const packs       = Math.ceil(scaledQty / item.packSize);
          const rowBg       = i % 2 === 0 ? '#fff' : '#f9f7f4';
          return `
            <tr style="background:${rowBg};">
              <td style="padding:5px 8px;">${item.name}</td>
              <td style="padding:5px 8px;text-align:right;font-weight:600;">${scaledQty.toLocaleString('en-IN')} ${item.unit}</td>
              <td style="padding:5px 8px;text-align:right;color:#4A7C59;">${packs} × ${item.packSize} ${item.packUnit}</td>
            </tr>
          `;
        }).join('')}
      </tbody>
    </table>
  `;
}

// ─── Diagnostic Lookup ────────────────────────────────────────────────────────

export function runDiagnosticLookup() {
  const sel = document.getElementById('diag-param');
  const out = document.getElementById('diag-output');
  if (!sel || !out) return;

  const key    = sel.value;
  const param  = DIAGNOSTIC_PARAMS[key];
  if (!param) {
    out.innerHTML = '<p style="color:#6b7280;font-style:italic;">Select a parameter above to view target range and remediation protocol.</p>';
    return;
  }

  out.innerHTML = `
    <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:1rem;margin-top:0.75rem;">
      <h4 style="color:#1E3A2B;font-weight:700;margin-bottom:0.5rem;">${param.label}</h4>
      <div style="margin-bottom:0.5rem;"><span style="font-weight:600;">Target Range:</span> <span style="color:#065f46;font-weight:700;">${param.targetRange}</span></div>
      <div style="margin-bottom:${param.caveat ? '0.5rem' : '0'};"><span style="font-weight:600;">Protocol:</span> ${param.protocol}</div>
      ${param.caveat ? `<div style="background:#fef9c3;border:1px solid #fde047;border-radius:6px;padding:0.6rem;color:#854d0e;font-size:0.85rem;margin-top:0.5rem;">${param.caveat}</div>` : ''}
    </div>
  `;
}

// ─── IPM / Health Cards ───────────────────────────────────────────────────────

export function renderHealthCards(filteredData) {
  const grid = document.getElementById('ipm-card-grid');
  if (!grid) return;

  if (!filteredData || filteredData.length === 0) {
    grid.innerHTML = '<p style="color:#6b7280;grid-column:1/-1;">No results found.</p>';
    return;
  }

  grid.innerHTML = filteredData.map(item => `
    <div class="ipm-card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
        <h4 style="color:#1E3A2B;font-weight:700;font-size:0.9rem;">${item.name}</h4>
        <span style="font-size:0.7rem;padding:2px 8px;border-radius:9999px;background:${item.category === 'insect' ? '#dbeafe' : '#fee2e2'};color:${item.category === 'insect' ? '#1e40af' : '#991b1b'};font-weight:600;">${item.category === 'insect' ? '🦟 Insect' : '🍄 Disease'}</span>
      </div>
      <table style="width:100%;font-size:0.78rem;border-collapse:collapse;">
        <tr><td style="padding:2px 4px;font-weight:600;color:#854d0e;width:32%;">ETL</td><td style="padding:2px 4px;">${item.etl}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#065f46;">Bio Control</td><td style="padding:2px 4px;">${item.bio}</td></tr>
        <tr><td style="padding:2px 4px;font-weight:600;color:#991b1b;">Chemical</td><td style="padding:2px 4px;">${item.chem}</td></tr>
        <tr style="background:#f9f7f4;"><td style="padding:2px 4px;font-weight:600;color:#4A7C59;">Description</td><td style="padding:2px 4px;">${item.desc}</td></tr>
      </table>
      <div style="margin-top:0.5rem;">
        <div style="font-weight:600;color:#4A7C59;font-size:0.78rem;margin-bottom:0.25rem;">Identification Symptoms:</div>
        <ul style="margin:0;padding-left:1.2rem;font-size:0.78rem;color:#374151;">
          ${item.fallbackSymptoms.map(s => `<li>${s}</li>`).join('')}
        </ul>
      </div>
    </div>
  `).join('');
}

export function filterHealthCards() {
  const searchEl = document.getElementById('ipm-search');
  const catEl    = document.getElementById('ipm-category');
  const query    = (searchEl?.value || '').toLowerCase().trim();
  const cat      = catEl?.value || 'all';

  let filtered = IPM_DATA;

  if (cat !== 'all') {
    filtered = filtered.filter(item => item.category === cat);
  }

  if (query) {
    filtered = filtered.filter(item =>
      item.name.toLowerCase().includes(query) ||
      item.desc.toLowerCase().includes(query) ||
      item.chem.toLowerCase().includes(query)
    );
  }

  renderHealthCards(filtered);
}

// ─── Event Bindings ───────────────────────────────────────────────────────────

function _bindEvents() {
  // IPM search and filter
  const ipmSearch = document.getElementById('ipm-search');
  const ipmCat    = document.getElementById('ipm-category');
  if (ipmSearch) ipmSearch.addEventListener('input',  filterHealthCards);
  if (ipmCat)    ipmCat.addEventListener('change',    filterHealthCards);

  // Financial simulator sliders
  ['sim-price', 'sim-yield2', 'sim-yield4', 'sim-bagcost'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', runFinancialSim);
  });

  // Irrigation calculator inputs
  ['irr-stage', 'irr-hardware'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', runIrrigationCalc);
  });
  const irrEta = document.getElementById('irr-efficiency');
  if (irrEta) irrEta.addEventListener('input', runIrrigationCalc);

  // Procurement slider
  const procSlider = document.getElementById('proc-trees');
  if (procSlider) procSlider.addEventListener('input', updateProcurement);
}

// ─── Bootstrap ───────────────────────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
  await _loadCharts();
  init();
  _bindEvents();
  switchTab('overview');
});
