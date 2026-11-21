/**
 * charts.js — Chart.js factory functions
 * All chart instances stored in _instances Map to prevent re-initialisation.
 * Imports data constants from ./charts-data.js
 */

import { loadChartJs } from './lazy.js';
import { TRANSLATIONS } from './i18n.js';
import {
  IRRIGATION_STAGES,
  ORCHARD
} from './charts-data.js';

// Module-level chart instance registry — prevents double-init on tab re-activation
const _instances = new Map();

// Brand colours
const C_PRIMARY   = '#1E3A2B';
const C_SECONDARY = '#4A7C59';
const C_ACCENT    = '#E07A5F';
const C_AMBER     = '#f59e0b';
const C_RED       = '#dc2626';
const C_BLUE      = '#3b82f6';

/**
 * _getOrCreate(canvasId, config)
 * Returns existing Chart instance if already created, otherwise creates new one.
 * Returns null (with console.warn) if canvas element not found.
 */
function _getOrCreate(canvasId, config) {
  if (_instances.has(canvasId)) return _instances.get(canvasId);

  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.warn('[Charts] Canvas not found:', canvasId);
    return null;
  }

  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, config);
  _instances.set(canvasId, chart);
  return chart;
}

// ─── Overview Tab Charts ──────────────────────────────────────────────────────

export async function initOverviewCharts() {
  await loadChartJs();
  // chart-water: Bar — daily water L/plant/day per stage at η=0.90
  const waterLabels = IRRIGATION_STAGES.map(s => s.label.split(' (')[0]); // short labels
  const waterData   = IRRIGATION_STAGES.map(s =>
    parseFloat(((s.et0 * s.kc * s.kr * 6.0) / 0.90).toFixed(2))
  );

  _getOrCreate('chart-water', {
    type: 'bar',
    data: {
      labels: waterLabels,
      datasets: [{
        label: 'Water (L/plant/day) 🟡C',
        data: waterData,
        backgroundColor: waterData.map((v, i) =>
          IRRIGATION_STAGES[i].id === '16' ? '#fee2e2' : C_SECONDARY + 'cc'
        ),
        borderColor: waterData.map((v, i) =>
          IRRIGATION_STAGES[i].id === '16' ? C_RED : C_PRIMARY
        ),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Daily Water Requirement per Plant by Growth Stage 🟡C',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'Formula: V = ET₀ × Kc × Kr × 6.0 m² ÷ η (η=0.90) — calibration required',
          color: '#6b7280',
          font: { size: 10 }
        },
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: { display: true, text: 'L/plant/day', color: '#6b7280' }
        },
        x: {
          ticks: { maxRotation: 45, font: { size: 9 } }
        }
      }
    }
  });

  // chart-npk: Doughnut — Year-2 N:P:K ratio 200:100:200
  _getOrCreate('chart-npk', {
    type: 'doughnut',
    data: {
      labels: ['N (200g)', 'P (100g)', 'K (200g)'],
      datasets: [{
        data: [200, 100, 200],
        backgroundColor: [C_SECONDARY, C_BLUE, C_AMBER],
        borderColor: ['#fff', '#fff', '#fff'],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Year-2 NPK Ratio (g/tree/yr) 🟡C',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'Calibrate with soil test after Year 1',
          color: '#6b7280',
          font: { size: 10 }
        },
        legend: { position: 'bottom' }
      }
    }
  });
}

// ─── Irrigation Tab Chart ─────────────────────────────────────────────────────

export async function initIrrigationChart() {
  await loadChartJs();
  const labels      = IRRIGATION_STAGES.map(s => s.label.split(' (')[0]);
  const perPlant    = IRRIGATION_STAGES.map(s =>
    parseFloat(((s.et0 * s.kc * s.kr * 6.0) / 0.90).toFixed(2))
  );
  const orchardKL   = perPlant.map(v => parseFloat((v * ORCHARD.trees / 1000).toFixed(1)));

  _getOrCreate('chart-irrigation', {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Per Plant (L/plant/day)',
          data: perPlant,
          borderColor: C_SECONDARY,
          backgroundColor: C_SECONDARY + '33',
          borderWidth: 2.5,
          fill: true,
          tension: 0.3,
          pointRadius: 5,
          yAxisID: 'yLeft'
        },
        {
          label: `Orchard Total (kL/day, ${ORCHARD.trees} trees)`,
          data: orchardKL,
          borderColor: C_ACCENT,
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          pointRadius: 4,
          borderDash: [6, 3],
          yAxisID: 'yRight'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Irrigation Water Demand by Growth Stage',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'V = ET₀ × Kc × Kr × S ÷ η  (S=6.0m², η=0.90)',
          color: '#6b7280',
          font: { size: 10 }
        }
      },
      scales: {
        yLeft: {
          type: 'linear',
          position: 'left',
          title: { display: true, text: 'L/plant/day', color: C_SECONDARY },
          beginAtZero: true
        },
        yRight: {
          type: 'linear',
          position: 'right',
          title: { display: true, text: 'kL/day (orchard)', color: C_ACCENT },
          beginAtZero: true,
          grid: { drawOnChartArea: false }
        },
        x: { ticks: { maxRotation: 40, font: { size: 9 } } }
      }
    }
  });
}

// ─── Honest charts (real API data only) ───────────────────────────────────────
// Each function writes a visible text summary and the canvas aria-label BEFORE Chart.js is
// requested. If Chart.js cannot load, the summary stays and a plain list replaces the canvas.
// Markup contract: <div class="sf-chart-block"><div class="sf-chart"><canvas id=...></canvas></div>
//                  <p class="sf-chart-summary"></p></div>

const C_LEAF = '#2F6B47';
const C_INK  = '#2B2D42';
const C_MUTE = '#4B5563';
const DONUT_COLOURS = ['#2F6B47', '#E07A5F', '#C98A1B', '#4F7CAC', '#8B6FB0', '#7C8A80'];
const FONT = { size: 12 };

function ct(key, vars = {}) {
  let lang = 'en';
  try { lang = localStorage.getItem('sf_lang') === 'hi' ? 'hi' : 'en'; } catch { /* ignore */ }
  let text = TRANSLATIONS[lang]?.[key] ?? TRANSLATIONS.en?.[key] ?? key;
  for (const [k, v] of Object.entries(vars)) text = text.split(`{{${k}}}`).join(String(v ?? ''));
  return text;
}

const rs = (v) => `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

function fd(iso) {
  const [y, m, d] = String(iso ?? '').slice(0, 10).split('-');
  return y && m && d ? `${d}/${m}/${y}` : '—';
}

const calm = () => {
  try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return false; }
};

function _parts(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) {
    console.warn('[Charts] Canvas not found:', canvasId);
    return null;
  }
  const block = canvas.closest('.sf-chart-block') || canvas.parentElement.parentElement;
  return { canvas, wrap: canvas.parentElement, block, summary: block.querySelector('.sf-chart-summary') };
}

function _showList(p, items) {
  p.wrap.classList.add('hidden');
  let ul = p.block.querySelector('.sf-chart-list');
  if (!ul) {
    ul = document.createElement('ul');
    ul.className = 'sf-chart-list';
    (p.summary || p.wrap).after(ul);
  }
  ul.replaceChildren(...items.map((text) => {
    const li = document.createElement('li');
    li.textContent = text;
    return li;
  }));
}

/** Text first, chart second. Returns the Chart instance, or null when only the text is shown. */
async function _draw(canvasId, { label, summary, items, config }) {
  const p = _parts(canvasId);
  if (!p) return null;
  p.canvas.setAttribute('role', 'img');
  p.canvas.setAttribute('aria-label', label);
  if (p.summary) p.summary.textContent = summary;
  p.block.querySelector('.sf-chart-list')?.remove();
  p.wrap.classList.remove('hidden');

  // Skeleton shimmer while Chart.js loads, so the box is never a plain empty rectangle.
  p.wrap.classList.add('sf-skeleton');
  const fallback = () => {
    p.wrap.classList.remove('sf-skeleton');
    if (p.summary) p.summary.textContent = `${ct('chart.unavailable')} ${summary}`;
    _showList(p, items);
    return null;
  };
  try { await loadChartJs(); } catch { return fallback(); }
  if (!p.canvas.isConnected) return null;   // the page re-rendered while Chart.js was loading
  if (typeof Chart === 'undefined') return fallback();

  const old = _instances.get(canvasId);
  if (old) { try { old.destroy(); } catch { /* ignore */ } _instances.delete(canvasId); }
  try {
    const chart = new Chart(p.canvas.getContext('2d'), config);
    _instances.set(canvasId, chart);
    p.wrap.classList.remove('sf-skeleton');
    return chart;
  } catch (err) {
    console.warn('[Charts] draw failed:', canvasId);
    return fallback();
  }
}

const tipKg = (ctx) => ` ${rs(ctx.parsed.x ?? ctx.parsed.y)}/kg`;

/**
 * Bar chart of the modal price (Rs/kg) per mandi. rows: [{label, value, best}] already sorted,
 * best first. meta: { date } the price date from the API.
 */
export function barMandi(canvasId, rows, meta = {}) {
  const best = rows.find((r) => r.best) || rows[0];
  const low = rows[rows.length - 1];
  const summary = rows.length > 1
    ? ct('chart.mandi.summary', { market: best.label, best: rs(best.value), n: rows.length, low: rs(low.value), date: fd(meta.date) })
    : ct('chart.mandi.summary1', { market: best.label, best: rs(best.value), date: fd(meta.date) });
  return _draw(canvasId, {
    label: ct('chart.mandi.label'),
    summary,
    items: rows.map((r) => `${r.label}: ${rs(r.value)}/kg${r.best ? ` (${ct('chart.mandi.best')})` : ''}`),
    config: {
      type: 'bar',
      data: {
        labels: rows.map((r) => r.label),
        datasets: [{
          label: ct('chart.mandi.series'),
          data: rows.map((r) => r.value),
          backgroundColor: rows.map((r) => (r.best ? C_ACCENT : C_LEAF)),
          borderRadius: 4,
          maxBarThickness: 26
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: calm() ? false : undefined,
        plugins: {
          legend: { display: false },
          tooltip: { bodyFont: FONT, titleFont: FONT, callbacks: { label: tipKg } }
        },
        scales: {
          x: { beginAtZero: true, ticks: { font: FONT, color: C_MUTE, callback: (v) => `₹${v}` } },
          y: { ticks: { font: FONT, color: C_INK } }
        }
      }
    }
  });
}

/** Line chart of saved daily modal prices. series: [{date, value}] oldest first, real rows only. */
export function lineHistory(canvasId, series, meta = {}) {
  const values = series.map((s) => s.value);
  const summary = ct('chart.history.summary', {
    n: series.length, from: fd(series[0].date), to: fd(series[series.length - 1].date),
    min: rs(Math.min(...values)), max: rs(Math.max(...values))
  });
  return _draw(canvasId, {
    label: ct('chart.history.label', { market: meta.market || '' }).trim(),
    summary,
    items: series.map((s) => `${fd(s.date)}: ${rs(s.value)}/kg`),
    config: {
      type: 'line',
      data: {
        labels: series.map((s) => fd(s.date).slice(0, 5)),
        datasets: [{
          label: ct('chart.history.series'),
          data: values,
          borderColor: C_PRIMARY,
          backgroundColor: 'rgba(47,107,71,0.15)',
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.2,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: calm() ? false : undefined,
        plugins: {
          legend: { display: false },
          tooltip: { bodyFont: FONT, titleFont: FONT, callbacks: { label: tipKg } }
        },
        scales: {
          x: { ticks: { font: FONT, color: C_MUTE, maxTicksLimit: 7 } },
          y: { ticks: { font: FONT, color: C_MUTE, callback: (v) => `₹${v}` } }
        }
      }
    }
  });
}

/** Doughnut of the farmer's own spending by type. rows: [{label, value}] with value > 0. */
export function donutCosts(canvasId, rows, total) {
  const sum = rows.reduce((s, r) => s + r.value, 0) || 1;
  const parts = rows.map((r) => `${r.label} ${rs(r.value)} (${Math.round((r.value / sum) * 100)}%)`);
  return _draw(canvasId, {
    label: ct('chart.donut.label'),
    summary: ct('chart.donut.summary', { total: rs(total), parts: parts.join(', ') }),
    items: parts,
    config: {
      type: 'doughnut',
      data: {
        labels: rows.map((r) => r.label),
        datasets: [{
          data: rows.map((r) => r.value),
          backgroundColor: rows.map((_, i) => DONUT_COLOURS[i % DONUT_COLOURS.length]),
          borderColor: '#fff',
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '58%',
        animation: calm() ? false : undefined,
        plugins: {
          legend: { position: 'bottom', labels: { font: FONT, color: C_INK, boxWidth: 12 } },
          tooltip: { bodyFont: FONT, titleFont: FONT, callbacks: { label: (ctx) => ` ${ctx.label}: ${rs(ctx.parsed)}` } }
        }
      }
    }
  });
}

/** Two bars: what the farmer spent and what the harvest earned. All three numbers come from the report. */
export function barRevenueCost(canvasId, { cost, revenue, profit }) {
  const net = profit == null ? '' : `${profit >= 0 ? '+' : '−'}${rs(Math.abs(profit))}`;
  return _draw(canvasId, {
    label: ct('chart.revcost.label'),
    summary: ct('chart.revcost.summary', { cost: rs(cost), revenue: rs(revenue), net: net || '—' }),
    items: [`${ct('chart.revcost.cost')}: ${rs(cost)}`, `${ct('chart.revcost.revenue')}: ${rs(revenue)}`],
    config: {
      type: 'bar',
      data: {
        labels: [ct('chart.revcost.cost'), ct('chart.revcost.revenue')],
        datasets: [{ data: [cost, revenue], backgroundColor: [C_ACCENT, C_LEAF], borderRadius: 4, maxBarThickness: 64 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: calm() ? false : undefined,
        plugins: {
          legend: { display: false },
          tooltip: { bodyFont: FONT, titleFont: FONT, callbacks: { label: (ctx) => ` ${rs(ctx.parsed.y)}` } }
        },
        scales: {
          x: { ticks: { font: FONT, color: C_INK } },
          y: { beginAtZero: true, ticks: { font: FONT, color: C_MUTE, callback: (v) => `₹${v}` } }
        }
      }
    }
  });
}