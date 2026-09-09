# Tasks: Taiwan Pink Guava Dashboard Rebuild

## Overview

40 implementation tasks across 7 phases. Each task is scoped for a single subagent pass. Tasks must be executed in order — later tasks depend on earlier ones.

---

## Phase 1: Scaffold

### Task 1: Create folder structure and empty files
- [x] 1.1 Create folder `css/` under the workspace root
- [x] 1.2 Create folder `js/` under the workspace root
- [x] 1.3 Create empty placeholder files: `css/style.css`, `js/data.js`, `js/translator.js`, `js/charts.js`, `js/app.js`
- [x] 1.4 Confirm all 5 files exist on disk before proceeding

**Files:** `css/style.css`, `js/data.js`, `js/translator.js`, `js/charts.js`, `js/app.js`
**Depends on:** nothing

---

### Task 2: Write `index.html` skeleton
- [x] 2.1 Add `<!DOCTYPE html>` head with charset, viewport, title ("Taiwan Pink Guava Master Plan")
- [x] 2.2 Add CDN `<link>` and `<script>` tags: Tailwind CSS v3 CDN, Chart.js CDN, Font Awesome 6 CDN
- [x] 2.3 Add inline Tailwind config `<script>` block extending colours: bg `#FDFBF7`, primary `#1E3A2B`, secondary `#4A7C59`, accent `#E07A5F`, dark `#2B2D42`
- [x] 2.4 Add language toggle bar div (fixed, `z-index:99999`) with `id="lang-en"` and `id="lang-hi"` buttons — NO Google Translate script, NO external translation calls
- [x] 2.5 Add sticky header with orchard title, status badge, and `<nav>` containing exactly 10 `<button>` elements with `id="btn-{slug}"`, `data-tab="{slug}"`, `onclick="switchTab('{slug}')"` — each `<span>` child has `data-i18n="nav.tab{N}"` — tab slugs: overview, market, nutrients, calendar, irrigation, fertigation, health, bagging, procurement, warnings
- [x] 2.6 Add `<main>` containing 10 `<section>` elements with `id="panel-{slug}"` class `"tab-panel"` — all panels except `panel-overview` have `hidden` attribute
- [x] 2.7 Add `<script type="module" src="js/app.js"></script>` before closing `</body>`

**Files:** `index.html`
**Depends on:** Task 1

---

### Task 3: Write `css/style.css`
- [x] 3.1 Add `.lang-active` rule: `background-color: #4A7C59; color: #fff; border: 2px solid #6ee7b7; border-radius: 20px;`
- [x] 3.2 Add `.tab-panel[hidden] { display: none; }` rule
- [x] 3.3 Add `.chart-container` rule: `position: relative; width: 100%; max-width: 650px; height: 320px; margin: auto;` plus `@media (max-width: 640px) { height: 260px; }`
- [x] 3.4 Add `.nav-btn.active` rule: `background-color: #1E3A2B; color: #fff; border-bottom: 3px solid #E07A5F;`
- [x] 3.5 Add `.nutrient-card`, `.ipm-card` card rules with white background, border `#E2DCD5`, border-radius 12px, hover box-shadow
- [x] 3.6 Add evidence badge rules: `.badge-A` (green-tinted), `.badge-B` (blue-tinted), `.badge-C` (amber-tinted), `.badge-E` (red-tinted)
- [x] 3.7 Add responsive grid overrides: `.kpi-grid` 2-col mobile, `.card-grid` 1-col mobile / 3-col desktop (`≥1024px`)
- [x] 3.8 Add `body { background-color: #FDFBF7; font-family: system-ui, sans-serif; }`

**Files:** `css/style.css`
**Depends on:** Task 1

---

### Task 4: Add `<link>` for `style.css` and spacer div in `index.html`
- [x] 4.1 Add `<link rel="stylesheet" href="css/style.css">` in the `<head>` of `index.html`
- [x] 4.2 Confirm the `<div style="height:44px;"></div>` spacer follows the language toggle bar so content is not hidden behind the fixed bar
- [x] 4.3 Verify the language toggle bar buttons have correct `onclick="setLang('en')"` / `onclick="setLang('hi')"` attributes (these will call into `app.js` which exposes them on window)

**Files:** `index.html`
**Depends on:** Tasks 2, 3

---

### Task 5: Smoke-test scaffold in browser
- [x] 5.1 Open `index.html` as `file://` in Chrome (or run a local check via Node's fs module) — no console errors expected at this stage
- [x] 5.2 Verify the fixed language bar is visible at top, navigation bar is visible, and Tab 1 panel is visible while others are hidden
- [x] 5.3 Confirm CDN resources load (Tailwind styles applied, Font Awesome icons visible in nav buttons)
- [x] 5.4 Note any layout issues for correction in later tasks

**Files:** (no file changes — verification only)
**Depends on:** Tasks 2, 3, 4

---

## Phase 2: Data Layer

### Task 6: Write orchard constants and financial scenario arrays in `data.js`
- [x] 6.1 Export `ORCHARD` object: `{ trees: 2100, avgFruitWeightKg: 0.400, spacingM2: 6.0 }`
- [x] 6.2 Export `OPEX_BASE` object: `{ yr2: 420000, yr4: 750000 }`
- [x] 6.3 Export `SCENARIO_YIELDS` array: `[20, 25, 30, 35, 40, 48]` (kg/tree — matches 6 scenario table rows)
- [x] 6.4 Export `SCENARIO_PRICES` array: `[40, 50, 60, 70, 85]` (₹/kg — matches 5 scenario table columns)
- [x] 6.5 Export `IRRIGATION_STAGES` array with 9 stage objects each having: `id`, `label`, `et0`, `kc`, `kr` — values must satisfy the ET₀×Kc×Kr×6÷η formula used in Requirements §8

**Files:** `js/data.js`
**Depends on:** Task 1

---

### Task 7: Write `NUTRIENTS_DATA` array in `data.js`
- [x] 7.1 Add all 14 NutrientEntry objects in order: N, P, K, Ca, Mg, S, Zn, B, Fe, Mn, Cu, Mo, Humic/Fulvic Acid, Biofertilizers
- [x] 7.2 Each entry must include fields: `id`, `symbol`, `name`, `category` (`'macro'|'secondary'|'micro'|'bio'`), `role`, `impact`, `deficiency`, `excess`, `doseDrip`, `doseFoliar`, `doseSoil`, `vertisol`, `antagonism`, `evidenceGrade`
- [x] 7.3 Every dosage string must include the evidence grade suffix (e.g. `"2.5 g/L 🟡C"`) — no absolute claims ("100% protection", "guaranteed")
- [x] 7.4 Entries for nutrients without cultivar-specific Vertisol validation must use `evidenceGrade: 'C'` and include a calibration note
- [x] 7.5 Add `imageLabel: '🔴 Illustrative only — not a deficiency photograph.'` to every entry

**Files:** `js/data.js`
**Depends on:** Task 6

---

### Task 8: Write `CALENDAR_DATA` array in `data.js`
- [x] 8.1 Add 13 CalendarEntry objects for months 8 through 20
- [x] 8.2 Each entry must include: `month`, `title`, `pheno`, `waterLpd` (numeric, computed from `ET₀×Kc×Kr×6÷0.90`), `waterFormula` (human-readable formula string with actual values), `fert`, `foliar`, `pruning`, `ipm`, `droughtStop`
- [x] 8.3 Set `droughtStop: true` only for Month 16 — water target text must include "SHUT OFF DRIP COMPLETELY"
- [x] 8.4 Verify all `waterLpd` values are consistent with the stage ET₀/Kc/Kr values in `IRRIGATION_STAGES`
- [x] 8.5 Month 8 entry must reference the 4 operational directives (deblossoming, canopy training, drainage furrows, biological inoculation)

**Files:** `js/data.js`
**Depends on:** Task 6

---

### Task 9: Write `IPM_DATA` array in `data.js`
- [x] 9.1 Add at minimum 8 IPMEntry objects: Oriental Fruit Fly, Guava Mealybug, Shoot & Fruit Borer, Bark-Eating Caterpillar, Guava Wilt Complex, Anthracnose & Dieback, Fruit Canker, Stylar End Rot
- [x] 9.2 Each entry must include: `id`, `category` (`'insect'|'disease'`), `name`, `etl`, `bio`, `chem` (with PHI where applicable), `desc`, `fallbackSymptoms` (array of symptom strings)
- [x] 9.3 Chemical recommendations must NOT include absolute efficacy claims; each `chem` field must note "verify CIB&RC registration before application"
- [x] 9.4 Add `FRAC_IRAC_ROTATION` array with 4 spray windows listing alternating mode-of-action groups for resistance management

**Files:** `js/data.js`
**Depends on:** Task 6

---

### Task 10: Write market research data constants in `data.js`
- [x] 10.1 Export `MONTHLY_PRICE_DATA` — 12 objects (Jan–Dec) each with `month`, `modal`, `min`, `max`, `arrivals`, `score` — use exact Azadpur Mandi values from the Market Strategy research: Jan modal ₹20, Feb ₹32, Mar ₹48, Apr ₹58, May ₹52, Jun ₹50, Jul ₹30, Aug ₹45, Sep ₹55, Oct ₹42, Nov ₹28, Dec ₹18
- [x] 10.2 Export `GRADE_ECONOMICS` — 4 objects (A+/A/B/C) each with `grade`, `label`, `weightG`, `pack`, `priceMin`, `priceMax`
- [x] 10.3 Export `BAHAR_COMPARISON` — 3 objects (Mrig/Ambe/Hasta) each with `name`, `flowering`, `harvest`, `priceRange`, `modal`, `verdict`, `score`
- [x] 10.4 Export `NET_REALIZATION_MODEL` — 2 objects (CFB carton vs plastic crate) with `protocol`, `grossMandi`, `totalDeductions`, `netFarmGate` — use research values: Grade A net ₹41.42/kg, Grade B net ₹23.69/kg
- [x] 10.5 Export `PROCUREMENT_BASE` object with three sub-objects (`fertilizers`, `bio`, `hardware`), each containing named items with `name`, `unit`, `qty2100` (base quantity for 2100 trees), `packSize`, `packUnit`
- [x] 10.6 Export `DIAGNOSTIC_PARAMS` object keyed by parameter slug (`ph`, `ece`, `oc`, `avp`, `caco3`, `rsc`, `sar`) each with `label`, `targetRange`, `protocol`, and for RSC/SAR a `caveat` noting dose must be calculated from actual water chemistry

**Files:** `js/data.js`
**Depends on:** Task 6

---

### Task 11: Write English translation strings in `data.js`
- [x] 11.1 Start `TRANSLATIONS` export with `en` object containing all keys for nav tab labels (`nav.tab1` through `nav.tab10`)
- [x] 11.2 Add English keys for Executive tab: `exec.kpi.*` (6 KPI labels), `exec.financial.*` (4 financial highlight labels), `exec.phase.*` (4 phase labels), `exec.directive.*` (4 directive headings)
- [x] 11.3 Add English keys for Market tab: `market.heading`, `market.chart.seasonal`, `market.chart.cashflow`, `market.chart.grade`, `market.chart.score`, `market.table.*` (column headers for scenario table and grade table), `market.bahar.*`, `market.net.*`
- [x] 11.4 Add English keys for `simulator.*` (all 4 slider labels, 4 output labels, disclaimer), `nutrient.*` (all card field labels + filter button labels + legend), `calendar.*` (month labels, detail card field labels)
- [x] 11.5 Add English keys for remaining tabs: `drip.*`, `fert.*`, `ipm.*` (search placeholder, category filter labels, regulatory disclaimer, card field labels), `bagging.*`, `procurement.*`, `warnings.*`
- [x] 11.6 Add `common.*` keys: `common.scenario`, `common.source`, `common.evidenceLegend.*` (4 grade descriptions), `common.disclaimer.financial`, `common.disclaimer.pesticide`

**Files:** `js/data.js`
**Depends on:** Tasks 7, 8, 9, 10

---

### Task 12: Write Hindi translation strings in `data.js`
- [x] 12.1 Add `hi` object to `TRANSLATIONS` — provide Hindi equivalents for all keys defined in Task 11
- [x] 12.2 Translate all 10 nav labels to Hindi (e.g. `'nav.tab1': 'डैशबोर्ड अवलोकन'`)
- [x] 12.3 Translate Executive tab KPI labels, financial highlights, phase labels, and directive headings
- [x] 12.4 Translate Market tab headings, chart titles, table headers, simulator labels, bahar comparison labels
- [x] 12.5 Translate Nutrient Master filter labels and all card field labels (role, deficiency, excess, timing, etc.)
- [x] 12.6 Translate remaining tabs: Calendar, Drip, Fertigation, IPM, Bagging, Procurement, Warnings, and all `common.*` keys — verify key count in `hi` matches key count in `en` (they must be equal)

**Files:** `js/data.js`
**Depends on:** Task 11

---

## Phase 3: Core Application Logic

### Task 13: Write `js/translator.js`
- [x] 13.1 Import `TRANSLATIONS` from `./data.js`
- [x] 13.2 Implement `setLanguage(lang)` function: `querySelectorAll('[data-i18n]')`, for each element read `data-i18n` key, look up `TRANSLATIONS[lang][key]`, set `el.textContent = text` if found, else `console.warn` with key and lang
- [x] 13.3 Implement `getCurrentLang()` returning the module-level `currentLang` variable
- [x] 13.4 Implement `init()` that calls `setLanguage('en')` once on first call (seeds initial English text)
- [x] 13.5 Update button active states in `setLanguage()`: toggle `.lang-active` class on `#lang-en` and `#lang-hi` based on active lang
- [x] 13.6 Export `setLanguage`, `getCurrentLang`, `init`

**Files:** `js/translator.js`
**Depends on:** Task 12

---

### Task 14: Write tab switching and bootstrapper in `js/app.js`
- [x] 14.1 Import `setLanguage`, `init` from `./translator.js`; import chart init functions from `./charts.js` (stub imports if charts.js is empty at this stage)
- [x] 14.2 Implement `switchTab(tabId)`: hide all `.tab-panel` elements (set `hidden`), remove `.active` from all `.nav-btn`, show `#panel-{tabId}` (remove `hidden`), add `.active` to `#btn-{tabId}`, call `_lazyInitCharts(tabId)`
- [x] 14.3 Implement `_lazyInitCharts(tabId)` with a `chartsInitialized` object — only call the appropriate chart init function on first activation of each tab
- [x] 14.4 Implement `window.switchTab` and `window.setLang` global wrappers so inline `onclick` attributes in HTML can call these functions from module scope
- [x] 14.5 Add `window.addEventListener('DOMContentLoaded', () => { init(); switchTab('overview'); })` bootstrapper

**Files:** `js/app.js`
**Depends on:** Task 13

---

### Task 15: Write Nutrient Master and Farm Calendar renderers in `js/app.js`
- [x] 15.1 Import `NUTRIENTS_DATA`, `CALENDAR_DATA` from `./data.js`
- [x] 15.2 Implement `renderNutrientCards(category)`: filter `NUTRIENTS_DATA` by `category` (or show all if `'all'`), build HTML for each nutrient card with all required fields and evidence badge, inject into `#nutrient-card-grid`
- [x] 15.3 Implement `filterNutrients(cat)`: called by filter button clicks; calls `renderNutrientCards(cat)` and manages active state on filter buttons
- [x] 15.4 Implement `renderCalendarButtons()`: build 13 month buttons (`Month 8` through `Month 20`) injecting into `#calendar-month-buttons`; bind click to `selectCalendarMonth(idx)`
- [x] 15.5 Implement `selectCalendarMonth(idx)`: look up `CALENDAR_DATA[idx]`, render detail card HTML (pheno, waterLpd with formula, fert, foliar, pruning, ipm) into `#calendar-detail`; if `droughtStop === true`, render water target in red with "SHUT OFF DRIP COMPLETELY" text

**Files:** `js/app.js`
**Depends on:** Tasks 7, 8, 14

---

### Task 16: Write calculator handler functions in `js/app.js`
- [x] 16.1 Import `ORCHARD`, `OPEX_BASE`, `IRRIGATION_STAGES`, `PROCUREMENT_BASE`, `DIAGNOSTIC_PARAMS` from `./data.js`
- [x] 16.2 Implement `runFinancialSim()`: read values from `#sim-price`, `#sim-yield2`, `#sim-yield4`, `#sim-bagcost` sliders; compute gross/net using formula from Design §4; update `#out-gross2`, `#out-net2`, `#out-gross4`, `#out-net4`; negative net income renders red with "−₹" prefix; attach `data-raw` attribute to each output element for test access
- [x] 16.3 Implement `runIrrigationCalc()`: read `#irr-stage`, `#irr-hardware`, `#irr-efficiency`; compute `volPerPlant = et0 × kc × kr × 6.0 / η`; compute run time from hardware dripper flow; display in `#irr-vol`, `#irr-runtime`, `#irr-orchard-total`
- [x] 16.4 Implement `updateProcurement()`: read `#proc-trees` slider value; for each item in `PROCUREMENT_BASE`, compute `Math.ceil(qty2100 × treeCount / 2100)` scaled quantity; render into `#proc-fertilizers`, `#proc-bio`, `#proc-hardware` panels showing both weight/count and commercial pack count
- [x] 16.5 Implement `runDiagnosticLookup()`: read selected value from `#diag-param` dropdown; look up in `DIAGNOSTIC_PARAMS`; render `targetRange` and `protocol` (and `caveat` for RSC/SAR) into `#diag-output`

**Files:** `js/app.js`
**Depends on:** Tasks 6, 10, 14

---

### Task 17: Write IPM search/filter and DOM initialisation in `js/app.js`
- [x] 17.1 Import `IPM_DATA` from `./data.js`
- [x] 17.2 Implement `renderHealthCards(filteredData)`: build HTML for each IPM card (name, ETL, bio, chem, description, fallback symptom list) and inject into `#ipm-card-grid`
- [x] 17.3 Implement `filterHealthCards()`: read `#ipm-search` text value and `#ipm-category` selected value; filter `IPM_DATA` by text (case-insensitive substring match on name + desc + chem) and by category; call `renderHealthCards()` with filtered result
- [x] 17.4 Wire all interactive elements on tab activation: when each tab first activates, call the relevant render/init function (nutrient cards for nutrients tab, calendar buttons for calendar tab, etc.)
- [x] 17.5 Add `oninput` event binding for `#ipm-search` and `onchange` for `#ipm-category` to call `filterHealthCards()` — and add `oninput` bindings for all 4 simulator sliders to call `runFinancialSim()`, for irrigation inputs to call `runIrrigationCalc()`, for procurement slider to call `updateProcurement()`

**Files:** `js/app.js`
**Depends on:** Tasks 9, 15, 16

---

## Phase 4: Charts

### Task 18: Write Executive Dashboard charts in `js/charts.js`
- [x] 18.1 Import `IRRIGATION_STAGES` from `./data.js`; set up module-level `_instances` Map for storing chart instances
- [x] 18.2 Implement `_getOrCreate(canvasId, config)` helper: return existing instance if present in `_instances`; otherwise create new `Chart`, store in map, and return it; return `null` with `console.warn` if canvas not found
- [x] 18.3 Implement `initOverviewCharts()`: create `chart-water` bar chart (X: stage labels, Y: L/plant/day computed as `et0 × kc × kr × 6.0 / 0.90`) using primary/secondary palette colours
- [x] 18.4 Implement doughnut chart `chart-npk`: 3 segments for Year-2 N:P:K ratio 200:100:200; labels "N (200g)", "P (100g)", "K (200g)"; colours green/blue/orange
xx- [-] 18.5 Export `initOverviewCharts`; ensure both charts are responsive and titled with evidence grade suffix `🟡C`

**Files:** `js/charts.js`
**Depends on:** Tasks 6, 7

---

### Task 19: Write Market tab price charts in `js/charts.js`
- [x] 19.1 Import `MONTHLY_PRICE_DATA` from `./data.js`
- [x] 19.2 Implement `initSeasonalChart()`: create `chart-seasonal` line chart with 3 datasets — modal price (solid green `#4A7C59`), min price (dashed amber), max price (dashed red); X-axis: 12 month labels; tooltip shows all three values plus arrivals pressure
- [x] 19.3 Implement `initScoreChart()`: create `chart-score` bar chart from `MONTHLY_PRICE_DATA[n].score`; bars coloured by score: `score ≤ 3` red, `4–6` amber, `≥ 7` green; Y-axis 0–10; label "Market Attractiveness Score (1–10)"
- [x] 19.4 Export both functions; include data source note "Source: Azadpur Mandi, Agmarknet — verified Sep 2026" as chart subtitle via Chart.js `plugins.subtitle`

**Files:** `js/charts.js`
**Depends on:** Task 10

---

### Task 20: Write Market tab cashflow and grade charts in `js/charts.js`
- [x] 20.1 Import `ORCHARD`, `OPEX_BASE`, `SCENARIO_PRICES` from `./data.js`
- [x] 20.2 Implement `initCashflowChart()`: create `chart-cashflow` combo bar+line chart showing 4-year cumulative cashflow using base case (yield2=18, yield4=30, price=SCENARIO_PRICES[2]=₹60); bar chart for annual net income, line for cumulative total; label all bars with "🔴 Scenario"
- [x] 20.3 Implement `initGradeChart()`: create `chart-grade` pie chart from `GRADE_ECONOMICS` representing illustrative revenue share (A+: 15%, A: 50%, B: 25%, C: 10%); label each slice with grade and price range; include disclaimer "🔴 Illustrative grade distribution"
- [x] 20.4 Add `initMarketCharts()` function that calls all four market chart inits in sequence: `initSeasonalChart()`, `initScoreChart()`, `initCashflowChart()`, `initGradeChart()`
- [x] 20.5 Export `initMarketCharts`

**Files:** `js/charts.js`
**Depends on:** Tasks 10, 19

---

### Task 21: Write Irrigation tab chart in `js/charts.js`
- [x] 21.1 Import `IRRIGATION_STAGES`, `ORCHARD` from `./data.js`
- [x] 21.2 Implement `initIrrigationChart()`: create `chart-irrigation` line chart showing daily water volume (L/plant/day) across all 9 growth stages at default η=0.90; X-axis: stage labels; Y-axis: litres/plant/day; single dataset in `#4A7C59`
- [x] 21.3 Add a second dataset for orchard total daily volume (L/day for 2100 trees) on a secondary Y-axis (right side)
- [x] 21.4 Include formula display `V = ET₀ × Kc × Kr × S ÷ η` as chart title or subtitle
- [x] 21.5 Export `initIrrigationChart`

**Files:** `js/charts.js`
**Depends on:** Tasks 6, 18

---

### Task 22: Wire charts into lazy-init system in `js/app.js`
- [x] 22.1 Import `initOverviewCharts`, `initMarketCharts`, `initIrrigationChart` from `./charts.js`
- [x] 22.2 Update `_lazyInitCharts(tabId)` switch statement to call the correct function for `'overview'`, `'market'`, `'irrigation'`
- [x] 22.3 Verify `chartsInitialized` guard prevents double-initialisation: switch away from overview, switch back, confirm no second Chart instance is created
- [x] 22.4 Confirm that tabs without charts (nutrients, calendar, fertigation, bagging, procurement, warnings) do not throw errors in `_lazyInitCharts`

**Files:** `js/app.js`
**Depends on:** Tasks 14, 18, 19, 20, 21

---

## Phase 5: Tab Content HTML

### Task 23: Write Tab 1 Executive Dashboard HTML in `index.html`
- [x] 23.1 Inside `#panel-overview`: add heading and intro paragraph with `data-i18n` attributes on all translatable text
- [x] 23.2 Add 6-cell KPI grid (`#exec-kpi-grid`) with fixed values: 2,100 trees, 8 months, Vertisol, Mrig Bahar, ₹60–₹85/kg 🔴, ~₹30 Lakhs/Yr 🔴 — all label `<span>` elements carry `data-i18n="exec.kpi.*"` keys
- [x] 23.3 Add 4 financial highlight cards: Year-2 first revenue, mature gross revenue, payback period, bagging premium — all with 🔴 scenario labels
- [x] 23.4 Add phenological progress bar section with 4 phase rows (Months 8–12, 13–15, 16–17, 18–24) — phase labels carry `data-i18n="exec.phase.*"`
- [x] 23.5 Add immediate directives panel (amber-bordered box) listing 4 Month-8 actions — each heading carries `data-i18n="exec.directive.*"`
- [x] 23.6 Add chart section with two `.chart-container` divs containing `<canvas id="chart-water">` and `<canvas id="chart-npk">`

**Files:** `index.html`
**Depends on:** Tasks 2, 11

---

### Task 24: Write Tab 2 Market & Financial Analytics HTML in `index.html`
- [x] 24.1 Inside `#panel-market`: add 4 interactive sliders with `id` attributes (`sim-price`, `sim-yield2`, `sim-yield4`, `sim-bagcost`), labels with `data-i18n="simulator.*"`, and `oninput="runFinancialSim()"` handlers
- [x] 24.2 Add simulator output section with 4 output divs (`out-gross2`, `out-net2`, `out-gross4`, `out-net4`) and "🔴 Scenario only" disclaimer
- [x] 24.3 Add static 6×5 scenario range table (6 yield rows × 5 price columns) showing gross revenue only; column headers and row labels carry `data-i18n="market.table.*"` — add footnote distinguishing gross from net
- [x] 24.4 Add Bahar Comparison panel (3-column grid) showing Mrig/Ambe/Hasta with pricing, verdict, and score — all headings translated
- [x] 24.5 Add Net Realization Model table comparing Grade A CFB carton (gross ₹65 → net ₹41.42/kg) vs Grade B plastic crate (gross ₹38 → net ₹23.69/kg) with all deduction line items
- [x] 24.6 Add Grade Economics table (A+/A/B/C rows with weight, pack type, price range) sourced from `GRADE_ECONOMICS`
- [x] 24.7 Add 4 chart canvases in `.chart-container` wrappers: `chart-seasonal`, `chart-score`, `chart-cashflow`, `chart-grade`

**Files:** `index.html`
**Depends on:** Tasks 2, 10, 11

---

### Task 25: Write Tab 3 Nutrient Master HTML in `index.html`
- [x] 25.1 Inside `#panel-nutrients`: add heading and evidence grade legend panel (4 rows: 🟢A, 🔵B, 🟡C, 🔴E with descriptions) — legend labels carry `data-i18n="common.evidenceLegend.*"`
- [x] 25.2 Add 5 filter buttons: All, Primary (N/P/K), Secondary (Ca/Mg/S), Micronutrients, Biostimulants — button labels carry `data-i18n="nutrient.filter.*"` — each has `onclick="filterNutrients('{cat}')"` where cat matches `category` values in `NUTRIENTS_DATA`
- [x] 25.3 Add empty `<div id="nutrient-card-grid" class="card-grid">` container where JS will inject cards
- [x] 25.4 Add disclaimer line: "🔴 All images are illustrative only — not deficiency photographs. Verify all dosages via soil and leaf tissue analysis."
- [x] 25.5 Confirm JS `renderNutrientCards('all')` will be called on tab first activation (hook in Task 17)

**Files:** `index.html`
**Depends on:** Tasks 2, 11

---

### Task 26: Write Tab 4 Farm Calendar HTML in `index.html`
- [x] 26.1 Inside `#panel-calendar`: add heading and instructions paragraph — heading carries `data-i18n="calendar.heading"`
- [x] 26.2 Add `<div id="calendar-month-buttons" class="flex flex-wrap gap-2">` container where JS will inject 13 month buttons
- [x] 26.3 Add `<div id="calendar-detail">` container where JS will inject the selected month's detail card
- [x] 26.4 Add a note explaining the water formula: "Water target computed from ET₀ × Kc × Kr × 6m² ÷ η (system efficiency)"
- [x] 26.5 Confirm JS `renderCalendarButtons()` and `selectCalendarMonth(0)` (Month 8 default) will be called on tab first activation

**Files:** `index.html`
**Depends on:** Tasks 2, 11

---

### Task 27: Write Tab 5 Drip Irrigation Calculator HTML in `index.html`
- [x] 27.1 Inside `#panel-irrigation`: add stage dropdown `<select id="irr-stage">` (9 options populated inline matching `IRRIGATION_STAGES` labels), hardware dropdown `<select id="irr-hardware">` (2 dripper × 4 L/h or 4 dripper × 4 L/h), efficiency input `<input type="number" id="irr-efficiency" min="0.70" max="1.00" step="0.01" value="0.90">`
- [x] 27.2 Add formula display section: static text "V = ET₀ × Kc × Kr × S ÷ η (S = 6.0 m²)" and output area with `#irr-vol`, `#irr-runtime`, `#irr-orchard-total` divs; all input labels carry `data-i18n="drip.*"`
- [x] 27.3 Add calculate button (or wire `oninput`/`onchange` events calling `runIrrigationCalc()`)
- [x] 27.4 Add `.chart-container` with `<canvas id="chart-irrigation">`
- [x] 27.5 Add Vertisol Drip Maintenance Protocol panel with 3 items: bi-weekly line flush, acid wash (with caveat that frequency depends on water test results), biofilm chlorination

**Files:** `index.html`
**Depends on:** Tasks 2, 11

---

### Task 28: Write Tab 6 Fertigation Schedules HTML in `index.html`
- [x] 28.1 Inside `#panel-fertigation`: add Annual RDF Targets panel (4 rows: Year 1, Year 2, Year 3, Mature Year 4+) showing N-P₂O₅-K₂O per tree with evidence grade badges — include ICAR-IIHR reference (340:70:260 g N:P₂O₅:K₂O) and note to calibrate after soil/leaf analysis
- [x] 28.2 Add 3-Tank Compatibility Protocol panel — clearly state Tank A contents (Calcium Nitrate + micronutrients), Tank B contents (mono/di ammonium phosphate + potassium nitrate), Tank C contents (WSF with sulfates if needed), and the prohibition on mixing Calcium Nitrate with Phosphates or Sulfates
- [x] 28.3 Add Stage 1 WSF Schedule table (Months 8–12, 16-week programme) with columns: Grade, Per plant/week (g), Per 100 trees/week (g), Orchard 2100 trees/week (kg), 16-week total (kg) — note that values are sourced from `data.js` constants, not hardcoded
- [x] 28.4 Add disclaimer: "🟡C — Mature NPK targets must be calibrated with soil test and leaf tissue analysis after Year 2"
- [x] 28.5 Ensure all column headers and panel headings carry `data-i18n="fert.*"` attributes

**Files:** `index.html`
**Depends on:** Tasks 2, 8, 9, 11

---

### Task 29: Write Tab 7 Crop Health & IPM HTML in `index.html`
- [x] 29.1 Inside `#panel-health`: add regulatory disclaimer BEFORE any IPM card content: "⚠ All chemical recommendations must be verified against current CIB&RC registration before application." — disclaimer text carries `data-i18n="ipm.disclaimer"`
- [x] 29.2 Add search input `<input id="ipm-search" type="text" placeholder="..." oninput="filterHealthCards()">` and category filter `<select id="ipm-category" onchange="filterHealthCards()">` with options All/Insect Pests/Diseases — placeholder and option labels carry `data-i18n="ipm.*"` keys
- [x] 29.3 Add empty `<div id="ipm-card-grid" class="card-grid">` for JS-rendered IPM cards
- [x] 29.4 Add Visual Disease Identification Gallery section with 8 identification cards — each card has either a `<img>` element (with `onerror` fallback hiding img and showing `.img-fallback` div) or a text-based symptom diagram; note "🔴 Image labels: illustrative only, not diagnostic photographs"
- [x] 29.5 Add FRAC/IRAC Resistance Rotation panel showing 4 spray windows with alternating mode-of-action groups for fungicide and insecticide rotation

**Files:** `index.html`
**Depends on:** Tasks 2, 9, 11

---

### Task 30: Write Tab 8 Fruit Bagging & Diagnostics HTML in `index.html`
- [x] 30.1 Inside `#panel-bagging`: add 3-layer bagging system description — Layer 1: EPE foam mesh inner, Layer 2: perforated LDPE middle, Layer 3: UV-reflective paper outer — with `🟡C` evidence badge and caveat "local validation required"
- [x] 30.2 Add pre-bagging spray directive: Azoxystrobin + Neem Oil, 24 hours before bagging, fruits must be dry — note chemical recommendations require CIB&RC verification
- [x] 30.3 Add diagnostic lookup section: `<select id="diag-param">` with at least 7 options (Soil pH, Soil ECe, Organic Carbon, Available Phosphorus, Free CaCO₃, Irrigation Water RSC, Irrigation Water SAR) plus a blank default option, with `onchange="runDiagnosticLookup()"`
- [x] 30.4 Add `<div id="diag-output">` where JS renders the target range and remediation protocol
- [x] 30.5 Add caveat panel: "RSC and SAR remediation doses must be calculated from actual water chemistry analysis — do not apply at a fixed rate"

**Files:** `index.html`
**Depends on:** Tasks 2, 10, 11

---

### Task 31: Write Tab 9 Procurement Calculator HTML in `index.html`
- [x] 31.1 Inside `#panel-procurement`: add tree count slider `<input type="range" id="proc-trees" min="100" max="5000" step="100" value="2100" oninput="updateProcurement()">` with live value display showing current tree count
- [x] 31.2 Add 3 output panels: `#proc-fertilizers` (Fertilizers & WSF), `#proc-bio` (Micronutrients & Bio-Agents), `#proc-hardware` (Hardware & Bagging Supplies) — panel headings carry `data-i18n="procurement.*"`
- [x] 31.3 Add note: "Base quantities keyed to 2,100 trees. Scaling formula: actual trees ÷ 2,100 × base quantity, rounded up to nearest whole commercial unit."
- [x] 31.4 Add note: "🔴 Prices and availability must be verified with local suppliers at time of purchase."
- [x] 31.5 Confirm `updateProcurement()` will be called on tab first activation to show default 2,100-tree quantities

**Files:** `index.html`
**Depends on:** Tasks 2, 10, 11

---

### Task 32: Write Tab 10 Critical Warnings HTML in `index.html`
- [x] 32.1 Inside `#panel-warnings`: add section heading and introductory note carrying `data-i18n="warnings.heading"` and `data-i18n="warnings.intro"`
- [x] 32.2 Add 9 warning cards (red/amber background), one each for: premature cropping, Vertisol root-collar waterlogging, tractor rotovation near trunk, glyphosate drift, calcium–phosphate tank mixing, unperforated plastic bagging, bloom-period insecticide spray, caustic chemical deblossoming, unbuffered water stress re-irrigation
- [x] 32.3 The chemical deblossoming warning card MUST clarify: spraying Urea or NAA on trees under 12 months is the prohibited action, and manual deblossoming is the recommended alternative
- [x] 32.4 Each warning card title and body carries `data-i18n="warnings.card{N}.*"` attributes for both title and body
- [x] 32.5 Use red background (`bg-red-50`, `border-red-500`) for severe warnings (premature cropping, waterlogging, caustic deblossoming) and amber (`bg-amber-50`, `border-amber-500`) for caution-level warnings

**Files:** `index.html`
**Depends on:** Tasks 2, 11

---

## Phase 6: Integration & QA

### Task 33: Add all `data-i18n` attributes across all 10 tab panels
- [x] 33.1 Audit `#panel-overview` — confirm every translatable static text span/heading/label carries a `data-i18n` key matching the `en` object in `TRANSLATIONS`
- [x] 33.2 Audit `#panel-market` and `#panel-nutrients` — same check; pay particular attention to table column headers (every `<th>`) and button labels
- [x] 33.3 Audit `#panel-calendar`, `#panel-irrigation`, `#panel-fertigation` — check all field labels and unit labels
- [x] 33.4 Audit `#panel-health`, `#panel-bagging`, `#panel-procurement`, `#panel-warnings` — check all labels
- [x] 33.5 Cross-check: count keys in `TRANSLATIONS.en` vs number of `data-i18n` attributes in HTML — these should match (every key used at least once, no orphaned keys)

**Files:** `index.html`
**Depends on:** Tasks 23–32, 12

---

### Task 34: Test language toggle end-to-end
- [x] 34.1 Open `index.html` as `file://` in Chrome; click "🇮🇳 हिन्दी" button — verify all `data-i18n` elements update to Hindi text
- [x] 34.2 Move a simulator slider while in Hindi mode — verify output values update correctly and remain numbers (not translated)
- [x] 34.3 Click "🇬🇧 English" button — verify all elements restore to English text
- [x] 34.4 Check browser console — verify zero errors, and that any `console.warn` messages are only for genuinely missing keys (fix any found missing keys in `data.js`)
- [x] 34.5 Verify `#lang-hi` has `.lang-active` class when Hindi is active, and `#lang-en` has it when English is active

**Files:** `js/data.js` (fix any missing keys), `index.html` (fix any missing `data-i18n` attributes)
**Depends on:** Tasks 13, 33

---

### Task 35: Test tab switching and chart lazy-init
- [x] 35.1 Click each of the 10 tab buttons in sequence — verify content section shows for each and all others are hidden
- [x] 35.2 Activate Market tab — verify all 4 charts render without blank canvases
- [x] 35.3 Switch away from Market tab and back — verify charts do NOT re-initialise (no duplicate chart error in console)
- [x] 35.4 Activate Irrigation tab — verify `chart-irrigation` renders; activate Overview tab — verify `chart-water` and `chart-npk` render
- [x] 35.5 Check console for any `"Canvas not found"` warnings and fix by ensuring all chart canvas IDs in `charts.js` match those in `index.html`

**Files:** `js/app.js`, `js/charts.js` (fix any canvas ID mismatches)
**Depends on:** Tasks 22, 23, 24, 27

---

### Task 36: Test financial simulator and irrigation calculator
- [x] 36.1 Set simulator sliders to: price=60, yield2=18, yield4=30, bagCost=2.75 — verify Year-2 gross = ₹2,268,000 (= 2100 × 18 × 60), Year-2 net = gross − (420000 + (2100×18/0.4 × 2.75))
- [x] 36.2 Set bagCost slider to maximum, reduce price slider to minimum — verify net income turns negative and renders in red with "−₹" prefix
- [x] 36.3 Test irrigation calculator: select Month 8-10 stage, η=0.90, 2 drippers × 4 L/h — verify volPerPlant output matches `ET₀ × Kc × Kr × 6.0 / 0.90` for that stage
- [x] 36.4 Verify procurement calculator at tree count 4200 shows exactly 2× the base quantities for each item (linear scaling test)
- [x] 36.5 Verify all simulator and calculator outputs carry "🔴 Scenario only" or equivalent disclaimer labels

**Files:** `js/app.js` (fix any formula errors found)
**Depends on:** Tasks 16, 24, 27, 31

---

### Task 37: Run syntax check and `file://` load verification
- [x] 37.1 Run `node --check js/app.js js/data.js js/translator.js js/charts.js` to verify no syntax errors in any JS file
- [x] 37.2 Open `index.html` as `file://` in Chrome with DevTools open — verify zero console errors on initial page load
- [x] 37.3 Open `index.html` as `file://` in Firefox — verify same: no errors, all 10 tabs accessible
- [x] 37.4 Open in Edge — verify language toggle and simulator both function
- [x] 37.5 Fix any identified syntax errors or module import path issues (ensure all imports use relative `./` paths)

**Files:** Any JS file with syntax errors found
**Depends on:** Tasks 14–22, 34–36

---

## Phase 7: Polish

### Task 38: Add disclaimer footer, evidence grade legend, and source attribution
- [x] 38.1 Add sticky footer or bottom-of-page panel with financial disclaimer text: "All financial projections are planning scenarios only (🔴 Scenario). Verify all prices with buyers before harvest. NHB/ICAR agronomic references used where stated."
- [x] 38.2 Add market data attribution in Market tab: "Price data: Azadpur Mandi, Agmarknet (verified Sep 2026). Production data: NHB Horticulture Statistics."
- [x] 38.3 Verify the evidence grade legend in the Nutrient Master tab covers all 4 grades with full descriptions
- [x] 38.4 Add CIB&RC disclaimer to IPM tab footer (visible even when cards are filtered out)
- [x] 38.5 Add ICAR-IIHR NPK reference in Fertigation tab: "Reference: ICAR-IIHR high-density guava research recommends 340:70:260 g N:P₂O₅:K₂O as an alternative calibration point"

**Files:** `index.html`
**Depends on:** Tasks 23–32

---

### Task 39: Mobile responsiveness fixes
- [x] 39.1 Test at 375px viewport width (Chrome DevTools mobile emulation) — verify navigation bar scrolls horizontally without wrapping to a second line
- [x] 39.2 Verify KPI grid in Tab 1 renders as 2-column on 375px (not 6-column)
- [x] 39.3 Verify nutrient card grid in Tab 3 renders as 1-column on mobile and 3-column on desktop ≥1024px
- [x] 39.4 Verify chart containers do not overflow their parent at 375px — confirm `height: 260px` on mobile is applied
- [x] 39.5 Verify scenario table in Tab 2 has horizontal scroll wrapper so it doesn't overflow on mobile: wrap in `<div class="overflow-x-auto">`

**Files:** `index.html`, `css/style.css` (fix any overflow issues found)
**Depends on:** Tasks 23–32, 3

---

### Task 40: Final content and compliance review
- [x] 40.1 Search entire `index.html` and `js/data.js` for prohibited absolute claims: "100% protection", "zero cracking", "guaranteed", "always" — remove or qualify any found
- [x] 40.2 Verify no location data more specific than "Badnawar Tehsil, Dhar District, Madhya Pradesh" appears in any user-visible text
- [x] 40.3 Verify all ₹ symbols display correctly across all tabs (UTF-8 encoding set in `<meta charset="UTF-8">`)
- [x] 40.4 Verify every financial projection in the simulator, scenario table, and financial highlight cards carries a "🔴 Scenario only" label
- [x] 40.5 Do a final cross-browser open in Chrome, Firefox, and Edge — confirm no regressions from Tasks 38–39

**Files:** `index.html`, `js/data.js`
**Depends on:** Tasks 38, 39
