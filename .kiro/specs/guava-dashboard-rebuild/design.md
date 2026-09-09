# Design Document: Taiwan Pink Guava Dashboard Rebuild

## Overview

The rebuilt dashboard is a pure client-side, single-page application (SPA) that runs directly from the local filesystem (`file://`) without a web server. It replaces a monolithic ~2,300-line HTML file with a clean 6-file architecture. The core design goals are:

1. **Maintainability** — each concern lives in exactly one file.
2. **Reliable bilingual toggle** — pre-translated Hindi strings swapped via DOM manipulation; zero network dependency, no Google Translate API.
3. **Consistent financial math** — all calculator logic derives from named constants; no magic numbers in rendering code.
4. **Data integrity** — evidence grades and scenario labels are embedded in the data layer, not the template layer.
5. **Market-accurate data** — verified Azadpur Mandi price data, grade economics, and net realization models from the Market Strategy research document are embedded as named constants.

---

## 1. File Architecture

```
index.html          ← HTML skeleton + CDN imports + Tailwind config + tab panels as empty divs
css/
  style.css         ← Custom CSS (chart containers, nav active states, card styles, lang toggle)
js/
  data.js           ← All datasets + Translation_Map (English & Hindi)
  translator.js     ← Language toggle engine (imports data.js)
  charts.js         ← Chart.js chart factories and update functions (imported by app.js)
  app.js            ← Tab router, calculator handlers, DOM renderers (imports data.js, charts.js, translator.js)
```

All files use ES module `import`/`export` syntax (`type="module"`). This works reliably as `file://` in Chrome 80+, Firefox 75+, and Edge 80+ without a bundler. Relative import paths are used throughout (e.g., `import { TRANSLATIONS } from './data.js'`).

### Dependency Graph

```
index.html
  └── loads: css/style.css
  └── loads (type="module"): js/app.js
        ├── imports: js/data.js        (all datasets, constants, translations)
        ├── imports: js/charts.js      (chart factories)
        └── imports: js/translator.js  (language engine)
              └── imports: js/data.js  (TRANSLATIONS map)
```

No global namespace pollution — all state is module-scoped.

---

## 2. Language Toggle Design

**Approach: pre-translated strings via `data-i18n` attributes.**

This is the critical feature. It works reliably as `file://` because it requires no network requests, no cookies, no reloads, and no external APIs.

### HTML Pattern

Every translatable element gets a `data-i18n="key"` attribute:

```html
<span data-i18n="nav.tab1">Dashboard Overview</span>
<button data-i18n="sim.btn.calculate">Calculate</button>
<th data-i18n="market.table.yield">Yield (kg/tree)</th>
```

### Translation Map in `data.js`

```js
export const TRANSLATIONS = {
  en: {
    'nav.tab1': 'Dashboard Overview',
    'nav.tab2': 'Market & Financial Analytics',
    'nav.tab3': 'Nutrient Master',
    'nav.tab4': 'Farm Calendar',
    'nav.tab5': 'Drip Irrigation Calculator',
    'nav.tab6': 'Fertigation Schedules',
    'nav.tab7': 'Crop Health & IPM',
    'nav.tab8': 'Fruit Bagging & Diagnostics',
    'nav.tab9': 'Procurement Calculator',
    'nav.tab10': 'Critical Warnings',
    // ... all other keys
  },
  hi: {
    'nav.tab1': 'डैशबोर्ड अवलोकन',
    'nav.tab2': 'बाजार और वित्तीय विश्लेषण',
    'nav.tab3': 'पोषक तत्व मास्टर',
    'nav.tab4': 'कृषि कैलेंडर',
    'nav.tab5': 'ड्रिप सिंचाई कैलकुलेटर',
    'nav.tab6': 'फर्टिगेशन शेड्यूल',
    'nav.tab7': 'फसल स्वास्थ्य और IPM',
    'nav.tab8': 'बैगिंग और डायग्नोस्टिक्स',
    'nav.tab9': 'खरीद कैलकुलेटर',
    'nav.tab10': 'महत्वपूर्ण चेतावनियाँ',
    // ... all other keys
  }
};
```

### `translator.js` Implementation

```js
import { TRANSLATIONS } from './data.js';

let currentLang = 'en';

export function init() {
  // Cache all translatable elements on first call
  _applyTranslation('en');
}

export function setLanguage(lang) {
  currentLang = lang;
  _applyTranslation(lang);
  document.getElementById('lang-en').classList.toggle('lang-active', lang === 'en');
  document.getElementById('lang-hi').classList.toggle('lang-active', lang === 'hi');
}

export function getCurrentLang() {
  return currentLang;
}

function _applyTranslation(lang) {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const text = TRANSLATIONS[lang]?.[key];
    if (text !== undefined) {
      el.textContent = text;
    } else {
      console.warn(`[Translator] Missing key: "${key}" for lang: "${lang}"`);
    }
  });
}
```

### Language Toggle HTML (fixed top bar)

```html
<div id="lang-bar" style="position:fixed; top:0; left:0; right:0; z-index:99999;
     background:#1E3A2B; padding:6px 16px; display:flex; align-items:center;
     justify-content:center; gap:12px;">
  <span style="color:#a7f3d0; font-size:12px; font-weight:600;">🌐 Language:</span>
  <button id="lang-en" class="lang-active" onclick="app.setLang('en')">🇬🇧 English</button>
  <button id="lang-hi" onclick="app.setLang('hi')">🇮🇳 हिन्दी</button>
</div>
<div style="height:44px;"></div>  <!-- spacer for fixed bar -->
```

### Translation Key Prefixes

| Prefix | Covers |
|--------|--------|
| `nav.*` | 10 tab navigation labels |
| `exec.*` | Executive dashboard KPI labels, directive headings, phase labels |
| `market.*` | Market tab headings, chart titles, table column headers, strategy cards |
| `simulator.*` | Financial simulator slider labels, output labels, disclaimer text |
| `nutrient.*` | Card field labels (role, deficiency, timing, dosage, antagonism, etc.) |
| `calendar.*` | Month selector labels, detail card field labels |
| `drip.*` | Irrigation calculator labels, formula display, maintenance protocol headings |
| `fert.*` | Fertigation tab headings, RDF table headers, tank protocol labels |
| `ipm.*` | IPM card field labels, search placeholder, disclaimer text |
| `bagging.*` | Bagging tab headings, diagnostic lookup labels |
| `procurement.*` | Procurement tab headings, slider label, panel titles |
| `warnings.*` | Warning card titles and body labels |
| `common.*` | Shared: "Scenario only", "Source", evidence grade legend labels, disclaimer footers |

**Dynamic content exclusion:** Calculator output values, chart data labels, and dynamically rendered card content are written directly by JS using constants — these elements do NOT carry `data-i18n` attributes and are never touched by the Translator. This is how Requirement 2.6 (preserve computed values) is satisfied.

---

## 3. Tab System

### HTML Structure

Each tab panel uses `hidden` attribute (not CSS `display:none`) for correct semantics:

```html
<section id="panel-overview" class="tab-panel">...</section>
<section id="panel-market"   class="tab-panel" hidden>...</section>
<!-- ... 8 more panels ... -->
```

Each nav button has an `id` and `data-tab` attribute:

```html
<button id="btn-overview" data-tab="overview" class="nav-btn active" onclick="switchTab('overview')">
  <i class="fa-solid fa-chart-pie"></i>
  <span data-i18n="nav.tab1">Dashboard Overview</span>
</button>
```

### Tab Router in `app.js`

```js
const chartsInitialized = {};

export function switchTab(tabId) {
  // Hide all panels
  document.querySelectorAll('.tab-panel').forEach(p => p.hidden = true);
  // Remove active class from all nav buttons
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  // Show target panel
  document.getElementById(`panel-${tabId}`).hidden = false;
  // Activate nav button
  document.getElementById(`btn-${tabId}`).classList.add('active');
  // Lazy chart initialisation — only on first activation
  if (!chartsInitialized[tabId]) {
    initChartsForTab(tabId);
    chartsInitialized[tabId] = true;
  }
}

function initChartsForTab(tabId) {
  switch (tabId) {
    case 'overview':     initOverviewCharts(); break;
    case 'market':       initMarketCharts();   break;
    case 'irrigation':   initIrrigationChart(); break;
    default: break;
  }
}
```

Tab 1 (overview) is the default active tab on page load.

---

## 4. Financial Simulator Design

### Constants in `data.js`

```js
export const ORCHARD = {
  trees: 2100,
  avgFruitWeightKg: 0.400,  // 400g average fruit weight
  spacingM2: 6.0             // 3.0m × 2.0m per tree
};

export const OPEX_BASE = {
  yr2: 420000,   // ₹4.2 Lakhs Year-2 base OPEX
  yr4: 750000    // ₹7.5 Lakhs Year-4+ base OPEX
};

export const SCENARIO_YIELDS = [20, 25, 30, 35, 40, 48]; // kg/tree rows
export const SCENARIO_PRICES = [40, 50, 60, 70, 85];     // ₹/kg columns
```

### Slider Ranges

| Slider | Min | Max | Default | Step |
|--------|-----|-----|---------|------|
| Average price (₹/kg) | 35 | 120 | 60 | 1 |
| Year-2 yield (kg/tree) | 10 | 30 | 18 | 1 |
| Mature yield Year 4+ (kg/tree) | 25 | 65 | 30 | 1 |
| Bagging & packing cost (₹/fruit) | 1.50 | 5.00 | 2.75 | 0.25 |

### Computation Formula

```js
function runFinancialSim() {
  const price    = parseFloat(document.getElementById('sim-price').value);
  const yield2   = parseFloat(document.getElementById('sim-yield2').value);
  const yield4   = parseFloat(document.getElementById('sim-yield4').value);
  const bagCost  = parseFloat(document.getElementById('sim-bagcost').value);

  const gross2   = ORCHARD.trees * yield2 * price;
  const fruits2  = (ORCHARD.trees * yield2) / ORCHARD.avgFruitWeightKg;
  const opex2    = OPEX_BASE.yr2 + (fruits2 * bagCost);
  const net2     = gross2 - opex2;

  const gross4   = ORCHARD.trees * yield4 * price;
  const fruits4  = (ORCHARD.trees * yield4) / ORCHARD.avgFruitWeightKg;
  const opex4    = OPEX_BASE.yr4 + (fruits4 * bagCost);
  const net4     = gross4 - opex4;

  renderSimOutput({ gross2, net2, gross4, net4 });
}
```

All four computed values must be displayed with "🔴 Scenario only" label. Negative net income renders in red, prefixed with "−₹".

---

## 5. Market Research Integration

All data below is sourced from the Market Strategy research document and stored as named constants in `data.js`.

### `MONTHLY_PRICE_DATA` (Azadpur Mandi Verified)

```js
export const MONTHLY_PRICE_DATA = [
  { month: 'Jan', modal: 20, min: 12, max: 35, arrivals: 'Very High (>180 t/day)', score: 2  },
  { month: 'Feb', modal: 32, min: 20, max: 45, arrivals: 'Moderate (80–120 t/day)', score: 6 },
  { month: 'Mar', modal: 48, min: 35, max: 65, arrivals: 'Low (40–70 t/day)',       score: 8 },
  { month: 'Apr', modal: 58, min: 45, max: 75, arrivals: 'Low (<40 t/day)',          score: 9 },
  { month: 'May', modal: 52, min: 40, max: 70, arrivals: 'Very Low (<30 t/day)',     score: 7 },
  { month: 'Jun', modal: 50, min: 30, max: 60, arrivals: 'Very Low (<35 t/day)',     score: 6 },
  { month: 'Jul', modal: 30, min: 20, max: 45, arrivals: 'Moderate (60–90 t/day)',   score: 4 },
  { month: 'Aug', modal: 45, min: 30, max: 80, arrivals: 'Moderate (70–110 t/day)',  score: 7 },
  { month: 'Sep', modal: 55, min: 35, max: 100, arrivals: 'Moderate-Low (60–90 t/day)', score: 9 },
  { month: 'Oct', modal: 42, min: 30, max: 65, arrivals: 'Moderate-High (90–130 t/day)', score: 7 },
  { month: 'Nov', modal: 28, min: 18, max: 45, arrivals: 'High (120–160 t/day)',     score: 5 },
  { month: 'Dec', modal: 18, min: 10, max: 30, arrivals: 'Extreme Peak (>200 t/day)', score: 2 }
];
```

### `GRADE_ECONOMICS`

```js
export const GRADE_ECONOMICS = [
  { grade: 'A+', label: 'Super Jumbo', weightG: '350–500', pack: 'CFB Carton + Foam Net', priceMin: 70, priceMax: 100 },
  { grade: 'A',  label: 'Premium',     weightG: '250–349', pack: 'CFB Carton + Foam Net', priceMin: 50, priceMax: 70  },
  { grade: 'B',  label: 'Economy',     weightG: '180–249', pack: 'Plastic Crate / Netted', priceMin: 30, priceMax: 45 },
  { grade: 'C',  label: 'Cull',        weightG: '<180',    pack: 'Loose Crates / Sacks',  priceMin: 12, priceMax: 22 }
];
```

### `NET_REALIZATION_MODEL`

```js
export const NET_REALIZATION_MODEL = [
  {
    protocol: 'Grade A — CFB Carton, Bagged (750km)',
    grossMandi: 65,
    totalDeductions: 23.58,
    netFarmGate: 41.42
  },
  {
    protocol: 'Grade B — Plastic Crate, Unbagged (750km)',
    grossMandi: 38,
    totalDeductions: 14.31,
    netFarmGate: 23.69
  }
];
```

### `BAHAR_COMPARISON`

```js
export const BAHAR_COMPARISON = [
  {
    name: 'Mrig Bahar',
    flowering: 'Jun–Jul',
    harvest: 'Nov–Jan',
    priceRange: '₹12–₹20/kg',
    modal: 18,
    verdict: '⚠ AVOID — Peak winter supply glut',
    score: 2
  },
  {
    name: 'Ambe Bahar',
    flowering: 'Feb–Mar',
    harvest: 'Aug–Sep',
    priceRange: '₹45–₹55/kg',
    modal: 50,
    verdict: '✓ VIABLE — Protective bagging essential',
    score: 7
  },
  {
    name: 'Hasta Bahar',
    flowering: 'Oct–Nov',
    harvest: 'Feb–Apr',
    priceRange: '₹48–₹58/kg',
    modal: 53,
    verdict: '✅ OPTIMAL — Spring supply deficit window',
    score: 9
  }
];
```

---

## 6. Data Architecture (`data.js`)

Complete export surface:

```js
// ─── Orchard & financial constants ────────────────────────────────────────
export const ORCHARD = { trees: 2100, avgFruitWeightKg: 0.400, spacingM2: 6.0 }
export const OPEX_BASE = { yr2: 420000, yr4: 750000 }
export const SCENARIO_YIELDS = [20, 25, 30, 35, 40, 48]
export const SCENARIO_PRICES = [40, 50, 60, 70, 85]

// ─── Agronomic datasets ───────────────────────────────────────────────────
export const NUTRIENTS_DATA = [...]      // 14 NutrientEntry objects
export const CALENDAR_DATA  = [...]      // 13 CalendarEntry objects (months 8–20)
export const IPM_DATA       = [...]      // 8+ IPMEntry objects
export const IRRIGATION_STAGES = [...]   // 9 IrrigationStage objects
export const FERTIGATION_DATA = { rdf: [...], stage1: [...], tanks: {...} }
export const PROCUREMENT_BASE = { fertilizers: [...], bio: [...], hardware: [...] }
export const DIAGNOSTIC_PARAMS = { ph: {...}, ec: {...}, oc: {...}, ... }

// ─── Market data (from research) ──────────────────────────────────────────
export const MONTHLY_PRICE_DATA = [...]  // Jan–Dec modal, min, max, score
export const GRADE_ECONOMICS = [...]     // A+/A/B/C specs and prices
export const BAHAR_COMPARISON = [...]    // 3 bahar types
export const NET_REALIZATION_MODEL = [...] // gross-vs-net deductions

// ─── Translation maps ─────────────────────────────────────────────────────
export const TRANSLATIONS = { en: {...}, hi: {...} }
```

---

## 7. Data Models

### NutrientEntry
```js
{
  id: string,               // "n", "p", "k", "ca", "mg", "s", "zn", "b", "fe", "mn", "cu", "mo", "ha", "bio"
  symbol: string,           // "N"
  name: string,             // "Nitrogen"
  category: 'macro' | 'secondary' | 'micro' | 'bio',
  role: string,
  impact: string,
  deficiency: string,
  excess: string,
  doseDrip: string,         // includes evidence grade suffix, e.g. "2.5 g/L 🟡C"
  doseFoliar: string,
  doseSoil: string,
  vertisol: string,
  antagonism: string,
  evidenceGrade: 'A' | 'B' | 'C' | 'E',
  imageLabel: string        // always "🔴 Illustrative only — not a deficiency photograph."
}
```

### CalendarEntry
```js
{
  month: number,            // 8–20
  title: string,            // "Month 8 — Vegetative Framework"
  pheno: string,
  waterLpd: number,         // litres/plant/day (computed from formula)
  waterFormula: string,     // "ET₀(4.2) × Kc(0.45) × Kr(0.26) × 6m² ÷ 0.90"
  fert: string,
  foliar: string,
  pruning: string,
  ipm: string,
  droughtStop: boolean      // true for month 16 only
}
```

### IPMEntry
```js
{
  id: string,
  category: 'insect' | 'disease',
  name: string,
  etl: string,
  bio: string,
  chem: string,             // includes PHI where applicable
  desc: string,
  fallbackSymptoms: string[]
}
```

### IrrigationStage
```js
{
  id: string,               // "8-10"
  label: string,            // "8–10 Months (Post-Monsoon)"
  et0: number,              // reference evapotranspiration mm/day
  kc: number,               // crop coefficient
  kr: number                // ground cover fraction
}
```

### EvidenceGrade
```js
// Attached to every dosage/claim in data arrays
{
  grade: 'A', label: '🟢 A — NHB/ICAR Official'
}
{
  grade: 'B', label: '🔵 B — Peer-reviewed research'
}
{
  grade: 'C', label: '🟡 C — Local adaptation, calibration required'
}
{
  grade: 'E', label: '🔴 E — Scenario/Forecast only'
}
```

---

## 8. Chart Specifications (`charts.js`)

All chart instances are stored in a module-level `Map<canvasId, ChartInstance>` to prevent re-initialisation on repeated tab switches.

| Chart ID | Type | Tab | Data Source | Notes |
|----------|------|-----|-------------|-------|
| `chart-water` | Bar | Executive | `IRRIGATION_STAGES` — L/plant/day per stage | X-axis: stage labels |
| `chart-npk` | Doughnut | Executive | Year-2 N:P:K ratio 200:100:200 | 3 segments |
| `chart-seasonal` | Line | Market | `MONTHLY_PRICE_DATA` modal + min/max bands | 3 datasets |
| `chart-score` | Bar | Market | `MONTHLY_PRICE_DATA` attractiveness scores | Color: red (≤3), amber (4-6), green (≥7) |
| `chart-cashflow` | Bar + Line | Market | Calculated from `ORCHARD`, `OPEX_BASE`, `SCENARIO_PRICES[2]` | 4-year trajectory |
| `chart-grade` | Pie | Market | `GRADE_ECONOMICS` — revenue share model | 4 segments |
| `chart-irrigation` | Line | Irrigation | Calculated ET₀×Kc×Kr per stage | 9 data points |

All chart canvases are wrapped in `.chart-container` (max-width 650px, height 320px). Charts use the custom colour palette (primary `#1E3A2B`, secondary `#4A7C59`, accent `#E07A5F`).

### Chart Factory Pattern

```js
// charts.js
import { IRRIGATION_STAGES, MONTHLY_PRICE_DATA, GRADE_ECONOMICS, ORCHARD, OPEX_BASE } from './data.js';

const _instances = new Map();

function _getOrCreate(canvasId, config) {
  if (_instances.has(canvasId)) return _instances.get(canvasId);
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) { console.warn('[Charts] Canvas not found:', canvasId); return null; }
  const chart = new Chart(ctx, config);
  _instances.set(canvasId, chart);
  return chart;
}

export function initOverviewCharts() {
  _getOrCreate('chart-water', { type: 'bar', data: buildWaterData(), options: chartOptions() });
  _getOrCreate('chart-npk',   { type: 'doughnut', data: buildNpkData(), options: doughnutOptions() });
}

export function initMarketCharts() {
  _getOrCreate('chart-seasonal',  buildSeasonalConfig());
  _getOrCreate('chart-score',     buildScoreConfig());
  _getOrCreate('chart-cashflow',  buildCashflowConfig());
  _getOrCreate('chart-grade',     buildGradeConfig());
}

export function initIrrigationChart() {
  _getOrCreate('chart-irrigation', buildIrrigationConfig());
}
```

---

## 9. CSS Architecture (`style.css`)

```css
/* Language toggle active state */
.lang-active {
  background-color: #4A7C59;
  color: #ffffff;
  border: 2px solid #6ee7b7;
}

/* Tab panel visibility — hidden attribute ensures no space taken */
.tab-panel[hidden] {
  display: none;
}

/* Chart container — prevents oversized canvas rendering */
.chart-container {
  position: relative;
  width: 100%;
  max-width: 650px;
  height: 320px;
  margin-left: auto;
  margin-right: auto;
}

@media (max-width: 640px) {
  .chart-container { height: 260px; }
}

/* Navigation active state */
.nav-btn.active {
  background-color: #1E3A2B;
  color: #ffffff;
  border-bottom: 3px solid #E07A5F;
}

/* Nutrient and IPM cards */
.nutrient-card,
.ipm-card {
  background: #ffffff;
  border: 1px solid #E2DCD5;
  border-radius: 12px;
  padding: 1.25rem;
  transition: box-shadow 0.15s ease;
}

.nutrient-card:hover,
.ipm-card:hover {
  box-shadow: 0 4px 16px rgba(30, 58, 43, 0.12);
}

/* Evidence grade badges */
.badge-A { background-color: #d1fae5; color: #065f46; }
.badge-B { background-color: #dbeafe; color: #1e40af; }
.badge-C { background-color: #fef9c3; color: #854d0e; }
.badge-E { background-color: #fee2e2; color: #991b1b; }

/* Responsive grid overrides (Tailwind utilities handle most of this,
   these rules handle cases Tailwind can't express) */
@media (max-width: 639px) {
  .kpi-grid   { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .card-grid  { grid-template-columns: repeat(1, minmax(0, 1fr)); }
}

@media (min-width: 1024px) {
  .card-grid  { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```

The Tailwind config extension lives in `index.html`'s inline `<script>` block:

```js
tailwind.config = {
  theme: {
    extend: {
      colors: {
        brand: {
          bg:        '#FDFBF7',
          primary:   '#1E3A2B',
          secondary: '#4A7C59',
          accent:    '#E07A5F',
          dark:      '#2B2D42'
        }
      }
    }
  }
}
```

---

## 10. Evidence Grade System

Every dosage or agronomic claim in `data.js` carries an `evidenceGrade` field using this scale:

| Grade | Badge | Source Criteria | Usage |
|-------|-------|-----------------|-------|
| `A` | `🟢 A` | NHB/ICAR official recommendation | NHB age-based fertiliser schedules, ICAR-IIHR high-density guava targets |
| `B` | `🔵 B` | Peer-reviewed research | Published trials on Psidium guajava or closely related cultivars |
| `C` | `🟡 C` | Local adaptation — calibration required | Rates not validated for this specific cultivar/Vertisol combination |
| `E` | `🔴 E` | Scenario/Forecast only | All financial projections and price estimates |

The legend is rendered as a static panel in the Nutrient Master tab and referenced in the footer.

Prohibited language: the application MUST NOT use "100% protection", "zero cracking", "guaranteed", "always", or equivalent absolute claims anywhere in user-visible text.

---

## 11. Responsive Layout

| Viewport | KPI grid | Nutrient/IPM cards | Nav bar |
|----------|----------|--------------------|---------|
| Mobile `< 640px` | 2 columns | 1 column | Horizontally scrollable, no wrap |
| Tablet `640–1023px` | 3 columns | 2 columns | Horizontally scrollable |
| Desktop `≥ 1024px` | 4–6 columns | 3 columns | Horizontally scrollable |

Nav bar uses `overflow-x: auto; white-space: nowrap;` to scroll on narrow viewports without wrapping.

---

## 12. Components and Interfaces

### Tab Router (`app.js`)
```js
export function switchTab(tabId)          // activates one panel, deactivates all others
```

### Translation Engine (`translator.js`)
```js
export function init()                    // call once on DOMContentLoaded
export function setLanguage(langCode)     // 'en' | 'hi'
export function getCurrentLang()          // returns active lang code
```

### Chart Factory (`charts.js`)
```js
export function initOverviewCharts()
export function initMarketCharts()
export function initIrrigationChart()
```

### Calculator Handlers (`app.js`)
```js
export function runFinancialSim()         // reads 4 sliders → writes 4 output divs
export function runIrrigationCalc()       // reads 3 inputs → writes 3 output divs
export function updateProcurement()       // reads 1 slider → writes 3 panels
export function filterNutrients(cat)      // shows/hides nutrient cards by category
export function filterHealthCards()       // text + category filter for IPM cards
export function runDiagnosticLookup()     // renders diagnostic text for selected param
export function selectCalendarMonth(idx)  // renders calendar detail card
```

---

## 13. Error Handling

### Missing Translation Keys
- **Detection**: `TRANSLATIONS[lang]?.[key]` is `undefined` during `setLanguage()`.
- **Response**: Leave existing text unchanged; emit `console.warn('[Translator] Missing key: "..." for lang: "..."')`.

### Chart Canvas Not Found
- **Detection**: `document.getElementById(canvasId)` returns `null`.
- **Response**: Return early; emit `console.warn('[Charts] Canvas not found:', canvasId)`.

### Image Load Failure (IPM Gallery)
- **Detection**: `<img>` element fires `onerror`.
- **Response**: Hide `<img>`; show adjacent `.img-fallback` div containing text-based symptom list.

### Calculator Invalid Input
- **Detection**: Value outside slider min/max.
- **Response**: Clamp to min/max before computing; no user-visible error.

### Negative Net Income
- **Detection**: Computed net income `< 0`.
- **Response**: Display in red text, prefixed with `"−₹"`, showing the absolute value.

---

## 14. Correctness Properties

### Property 1: Hindi translation completeness
For any element carrying `data-i18n` attribute with key K, after calling `setLanguage('hi')`, the element's `textContent` SHALL equal `TRANSLATIONS.hi[K]`.

**Validates: Requirement 2.2**

---

### Property 2: Round-trip language restoration
For any element carrying `data-i18n` attribute with key K, after `setLanguage('hi')` then `setLanguage('en')`, the element's `textContent` SHALL equal `TRANSLATIONS.en[K]`.

**Validates: Requirement 2.3**

---

### Property 3: Translation does not mutate calculator outputs
For any valid slider state S that produces computed output values V, calling `setLanguage('hi')` SHALL NOT change the text content of any calculator output element. Reading output values after translation SHALL return V.

**Validates: Requirement 2.6**

---

### Property 4: Tab exclusivity invariant
For any tab ID T in the set of 10 tab slugs, after `switchTab(T)`, exactly one `.tab-panel` SHALL be visible (`hidden` attribute absent), and it SHALL be the panel with `id="panel-" + T`.

**Validates: Requirement 3.2**

---

### Property 5: Financial simulator formula correctness
For any valid input combination `(price ∈ [35,120], yield2 ∈ [10,30], yield4 ∈ [25,65], bagCost ∈ [1.5,5.0])`:
```
gross2 = ORCHARD.trees × yield2 × price
fruits2 = (ORCHARD.trees × yield2) / ORCHARD.avgFruitWeightKg
net2 = gross2 − (OPEX_BASE.yr2 + fruits2 × bagCost)
```
The displayed Year-2 gross and net output values SHALL equal these computed values.

**Validates: Requirements 5.2, 5.3**

---

### Property 6: Nutrient filter exclusivity
For any category value F ∈ `{'macro','secondary','micro','bio'}`, after `filterNutrients(F)`, every visible Nutrient_Card's `data-category` attribute SHALL equal F.

**Validates: Requirement 6.3**

---

### Property 7: Irrigation calculator formula correctness
For any valid stage index I and efficiency `η ∈ [0.70, 0.98]`:
```
volPerPlant = ET₀ × Kc × Kr × ORCHARD.spacingM2 / η
orchardTotal = volPerPlant × ORCHARD.trees
```
The Drip_Irrigation_Calculator SHALL display these values.

**Validates: Requirement 8.2**

---

### Property 8: IPM search filter correctness
For any non-empty query string Q, every IPM_Card visible after text filtering SHALL contain Q (case-insensitive) in at least one of: name, description, or chemical recommendation text.

**Validates: Requirement 10.2**

---

### Property 9: Procurement linear scaling correctness
For any tree count `T ∈ [100, 5000]`, every procurement quantity displayed SHALL equal `Math.ceil(BASE_QUANTITY × T / ORCHARD.trees)` where `BASE_QUANTITY` is the corresponding constant from `PROCUREMENT_BASE`.

**Validates: Requirements 12.2, 12.3**

---

## 15. Testing Strategy

### Unit Tests (example-based)

Tests are written as a self-contained `tests/test-runner.html` that loads all JS modules and runs assertions inline — no build step, works via `file://`.

- **translator.js**: Verify `setLanguage('hi')` updates a known `data-i18n` element; verify missing-key fallback; verify round-trip restoration.
- **Financial simulator**: Verify formula for one known input set (price=60, yield2=18, yield4=30, bagCost=2.75).
- **Irrigation calculator**: Verify formula for one known stage (month 8–10, η=0.90).
- **Procurement scaling**: Verify output for T=4200 (2× base) and T=1050 (0.5× base).
- **Tab routing**: Verify `switchTab('nutrients')` produces exactly one visible panel.

### Property-Based Tests

Loaded via `tests/property-tests.html` using fast-check CDN. Minimum 100 iterations per property.

```js
// Property 5 example — Financial simulator formula correctness
// Feature: guava-dashboard-rebuild, Property 5
fc.assert(fc.property(
  fc.float({ min: 35, max: 120 }),
  fc.integer({ min: 10, max: 30 }),
  fc.integer({ min: 25, max: 65 }),
  fc.float({ min: 1.5, max: 5.0 }),
  (price, yield2, yield4, bagCost) => {
    const expectedGross2 = ORCHARD.trees * yield2 * price;
    const fruits2 = (ORCHARD.trees * yield2) / ORCHARD.avgFruitWeightKg;
    const expectedNet2 = expectedGross2 - (OPEX_BASE.yr2 + fruits2 * bagCost);
    runFinancialSim({ price, yield2, yield4, bagCost });
    const displayedGross2 = parseFloat(document.getElementById('out-gross2').dataset.raw);
    const displayedNet2   = parseFloat(document.getElementById('out-net2').dataset.raw);
    return Math.abs(displayedGross2 - expectedGross2) < 0.01 &&
           Math.abs(displayedNet2   - expectedNet2)   < 0.01;
  }
), { numRuns: 100 });
```

**Properties to test:** 1 through 9 as listed in Section 14.

### Integration Checks

- Open `index.html` via `file://` in Chrome, Firefox, Edge — verify no console errors.
- Click all 10 tabs — verify content renders, charts initialise once.
- Toggle language to Hindi and back — verify all `data-i18n` elements update, calculator outputs unchanged.
- Move all sliders — verify outputs update, negative net income shows in red.
