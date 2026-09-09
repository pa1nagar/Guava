/**
 * charts.js — Chart.js factory functions
 * All chart instances stored in _instances Map to prevent re-initialisation.
 * Imports data constants from ./data.js
 */

import {
  IRRIGATION_STAGES,
  MONTHLY_PRICE_DATA,
  GRADE_ECONOMICS,
  ORCHARD,
  OPEX_BASE,
  SCENARIO_PRICES
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

// ─── Market Tab Charts ────────────────────────────────────────────────────────

function initSeasonalChart() {
  const months = MONTHLY_PRICE_DATA.map(d => d.month);

  _getOrCreate('chart-seasonal', {
    type: 'line',
    data: {
      labels: months,
      datasets: [
        {
          label: 'Modal Price (₹/kg)',
          data: MONTHLY_PRICE_DATA.map(d => d.modal),
          borderColor: C_SECONDARY,
          backgroundColor: C_SECONDARY + '22',
          borderWidth: 2,
          fill: false,
          tension: 0.3,
          pointRadius: 4
        },
        {
          label: 'Min Price (₹/kg)',
          data: MONTHLY_PRICE_DATA.map(d => d.min),
          borderColor: C_AMBER,
          borderDash: [5, 5],
          borderWidth: 1.5,
          fill: false,
          tension: 0.3,
          pointRadius: 2
        },
        {
          label: 'Max Price (₹/kg)',
          data: MONTHLY_PRICE_DATA.map(d => d.max),
          borderColor: C_RED,
          borderDash: [5, 5],
          borderWidth: 1.5,
          fill: false,
          tension: 0.3,
          pointRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Seasonal Price Trends — Azadpur Mandi',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'Source: Azadpur Mandi, Agmarknet — verified Sep 2026',
          color: '#6b7280',
          font: { size: 10 }
        },
        tooltip: {
          callbacks: {
            afterBody: (items) => {
              const idx = items[0]?.dataIndex;
              if (idx !== undefined) {
                return [`Arrivals: ${MONTHLY_PRICE_DATA[idx].arrivals}`];
              }
              return [];
            }
          }
        }
      },
      scales: {
        y: {
          title: { display: true, text: '₹/kg', color: '#6b7280' },
          beginAtZero: true
        }
      }
    }
  });
}

function initScoreChart() {
  const months = MONTHLY_PRICE_DATA.map(d => d.month);
  const scores = MONTHLY_PRICE_DATA.map(d => d.score);
  const colors = scores.map(s =>
    s <= 3 ? C_RED + 'cc' : s <= 6 ? C_AMBER + 'cc' : C_SECONDARY + 'cc'
  );

  _getOrCreate('chart-score', {
    type: 'bar',
    data: {
      labels: months,
      datasets: [{
        label: 'Market Attractiveness Score (1–10)',
        data: scores,
        backgroundColor: colors,
        borderColor: colors.map(c => c.replace('cc', '')),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Monthly Market Attractiveness Score (1–10)',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'Source: Azadpur Mandi, Agmarknet — verified Sep 2026',
          color: '#6b7280',
          font: { size: 10 }
        },
        legend: { display: false }
      },
      scales: {
        y: { min: 0, max: 10, title: { display: true, text: 'Score', color: '#6b7280' } }
      }
    }
  });
}

function initCashflowChart() {
  const price  = SCENARIO_PRICES[2]; // ₹60 base case
  const y2     = 18; const y4 = 30;

  const fruits2 = (ORCHARD.trees * y2) / ORCHARD.avgFruitWeightKg;
  const net2    = (ORCHARD.trees * y2 * price) - (OPEX_BASE.yr2 + fruits2 * 2.75);
  const fruits4 = (ORCHARD.trees * y4) / ORCHARD.avgFruitWeightKg;
  const net4    = (ORCHARD.trees * y4 * price) - (OPEX_BASE.yr4 + fruits4 * 2.75);

  const annualNet  = [0, net2, net4, net4]; // Yr1 no harvest
  const cumulative = annualNet.reduce((acc, v, i) => {
    acc.push((acc[i - 1] || 0) + v);
    return acc;
  }, []);

  _getOrCreate('chart-cashflow', {
    type: 'bar',
    data: {
      labels: ['Year 1', 'Year 2', 'Year 3', 'Year 4'],
      datasets: [
        {
          type: 'bar',
          label: 'Annual Net Income 🔴 Scenario',
          data: annualNet,
          backgroundColor: annualNet.map(v => v >= 0 ? C_SECONDARY + 'aa' : C_RED + 'aa'),
          borderColor:     annualNet.map(v => v >= 0 ? C_PRIMARY : C_RED),
          borderWidth: 1,
          yAxisID: 'y'
        },
        {
          type: 'line',
          label: 'Cumulative Total 🔴 Scenario',
          data: cumulative,
          borderColor: C_ACCENT,
          borderWidth: 2.5,
          fill: false,
          pointRadius: 5,
          tension: 0.2,
          yAxisID: 'y'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: '4-Year Cashflow Projection 🔴 Scenario (base: ₹60/kg, Y2=18kg, Y4=30kg)',
          color: C_PRIMARY,
          font: { size: 12, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: 'Scenario only — verify with actual buyer prices',
          color: '#dc2626',
          font: { size: 10 }
        }
      },
      scales: {
        y: { title: { display: true, text: '₹', color: '#6b7280' } }
      }
    }
  });
}

function initGradeChart() {
  _getOrCreate('chart-grade', {
    type: 'pie',
    data: {
      labels: GRADE_ECONOMICS.map(g => `${g.grade} — ${g.label} (₹${g.priceMin}–${g.priceMax}/kg)`),
      datasets: [{
        data: [15, 50, 25, 10], // Illustrative revenue share %
        backgroundColor: [C_PRIMARY, C_SECONDARY, C_AMBER, C_RED],
        borderColor: ['#fff', '#fff', '#fff', '#fff'],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Illustrative Revenue Share by Grade 🔴',
          color: C_PRIMARY,
          font: { size: 13, weight: 'bold' }
        },
        subtitle: {
          display: true,
          text: '🔴 Illustrative grade distribution — not a production forecast',
          color: '#dc2626',
          font: { size: 10 }
        },
        legend: { position: 'bottom', labels: { font: { size: 9 } } }
      }
    }
  });
}

export function initMarketCharts() {
  initSeasonalChart();
  initScoreChart();
  initCashflowChart();
  initGradeChart();
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
