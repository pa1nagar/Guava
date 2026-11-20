/**
 * lazy.js - load Chart.js on first use so it never blocks first paint.
 */
const CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js";
let _chartPromise = null;

export function loadChartJs() {
  if (window.Chart) return Promise.resolve(window.Chart);
  if (!_chartPromise) {
    _chartPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = CHART_JS_URL;
      s.async = true;
      s.onload = () => resolve(window.Chart);
      s.onerror = () => { _chartPromise = null; s.remove(); reject(new Error("Chart.js failed to load")); };
      document.head.appendChild(s);
    });
  }
  return _chartPromise;
}