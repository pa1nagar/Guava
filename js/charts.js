/**
 * charts.js — Chart.js factory functions
 * All chart instances stored in _instances Map to prevent re-initialisation.
 * Imports data constants from ./data.js
 */

import {
  IRRIGATION_STAGES,
  ORCHARD
} from './data.js';

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

export function initOverviewCharts() {
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

export function initIrrigationChart() {
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
