# Requirements Document

## Introduction

A full rebuild of the Taiwan Pink Guava Orchard Master Plan Dashboard — a single-page, client-side web application for managing a 2,100-tree commercial Taiwan Pink Guava (*Psidium guajava* L.) orchard in Badnawar Tehsil, Dhar District, Madhya Pradesh. The rebuild replaces a monolithic ~2,300-line single HTML file with a clean multi-file architecture, adds a reliable bilingual (English/Hindi) toggle using pre-translated strings, corrects financial calculator inconsistencies, and hardens all agronomic claims with proper evidence grading. The application must run entirely from the local filesystem (`file://`) without a web server.

## Glossary

- **Dashboard**: The single-page web application described in this document.
- **Translator**: The JavaScript module responsible for switching UI language between English and Hindi.
- **Language_Toggle**: The pair of buttons (🇬🇧 English | 🇮🇳 हिन्दी) that switch the active language.
- **Translation_Map**: A parallel JavaScript object in `data.js` that holds all UI strings in both languages, keyed by unique `data-i18n` identifiers.
- **Tab**: One of the 10 named content sections navigated via the top navigation bar.
- **Financial_Simulator**: The interactive ROI calculator in the Market & Financial Analytics tab.
- **Nutrient_Card**: A visual card component representing one of the 14 agronomic nutrients or biostimulants.
- **Evidence_Grade**: A coloured emoji badge (🟢A / 🔵B / 🟡C / 🔴E) indicating the reliability level of an agronomic claim.
- **IPM_Card**: A visual card representing a pest or disease with biocontrol, chemical, and regulatory information.
- **Diagnostic_Lookup**: The interactive dropdown in the Bagging & Diagnostics tab for soil and water parameters.
- **Procurement_Calculator**: The slider-based calculator that scales input quantities to any orchard size.
- **ET0**: Reference evapotranspiration (mm/day), an input to the drip irrigation formula.
- **Kc**: Crop coefficient, stage-dependent scalar on ET0.
- **Kr**: Ground cover fraction, canopy-based reduction factor.
- **WSF**: Water-Soluble Fertilizer — fertilizer grades dissolved into drip fertigation water.
- **RDF**: Recommended Dose of Fertilizer.
- **Vertisol**: Black clay soil type present at the orchard site; high shrink-swell, alkaline pH 7.8–8.2.
- **Mrig_Bahar**: The monsoon-bloom/winter-harvest crop cycle deliberately induced to avoid peak pest pressure.
- **EARS**: Easy Approach to Requirements Syntax — the structured requirement language used in this document.

---

## Requirements

### Requirement 1: Multi-File Project Architecture

**User Story:** As a developer, I want the application code split into well-defined files, so that each concern can be maintained independently without searching through thousands of lines.

#### Acceptance Criteria

1. THE Dashboard SHALL be composed of exactly these output files: `index.html`, `css/style.css`, `js/app.js`, `js/data.js`, `js/charts.js`, `js/translator.js`.
2. THE `index.html` file SHALL contain only structural markup (HTML skeleton, CDN `<script>` and `<link>` tags, tab panels as empty containers); it SHALL NOT contain inline `<style>` blocks or `<script>` logic blocks beyond module imports.
3. THE `js/data.js` file SHALL export all agronomic datasets (nutrients, calendar, IPM, fertigation tables) and both the English and Hindi Translation_Maps as named constants.
4. THE `js/app.js` file SHALL contain all tab-switching logic, calculator event handlers, and DOM-rendering functions; it SHALL import from `data.js`.
5. THE `js/charts.js` file SHALL contain all Chart.js chart initialisation and update functions; it SHALL be imported by `app.js`.
6. THE `js/translator.js` file SHALL contain the Translator module; it SHALL import the Translation_Map from `data.js`.
7. THE `css/style.css` file SHALL contain all custom CSS rules not expressible via Tailwind utility classes.
8. WHEN the application is opened as a `file://` URL in Chrome, Firefox, or Edge, THE Dashboard SHALL load all tabs and language toggle without error.

---

### Requirement 2: Bilingual Language Toggle

**User Story:** As an orchard manager who reads Hindi, I want to switch the entire dashboard to Hindi instantly, so that I can share it with workers and family members who cannot read English.

#### Acceptance Criteria

1. THE Dashboard SHALL display a Language_Toggle bar fixed at the top of every page with exactly two buttons: "🇬🇧 English" and "🇮🇳 हिन्दी".
2. WHEN the user clicks "🇮🇳 हिन्दी", THE Translator SHALL replace every visible UI string with its Hindi equivalent from the Translation_Map without reloading the page.
3. WHEN the user clicks "🇬🇧 English", THE Translator SHALL restore every UI string to its English original without reloading the page.
4. THE Translator SHALL NOT use the Google Translate API, any external translation service, or any network request to perform translation.
5. THE Translation_Map SHALL cover: navigation labels, tab headings, all KPI card labels, all table column headers, all button labels, all disclaimer and warning text, and all nutrient card field labels.
6. WHEN translation is applied, THE Dashboard SHALL preserve all dynamic computed values (calculator outputs, chart data labels) and SHALL NOT reset or clear them.
7. IF a Translation_Map key is missing for a given element, THEN THE Translator SHALL leave the existing text unchanged and SHALL log a warning to the browser console.
8. WHEN the active language is Hindi, THE "🇮🇳 हिन्दी" button SHALL appear visually active (filled background) and the "🇬🇧 English" button SHALL appear inactive.
9. WHEN the active language is English, THE "🇬🇧 English" button SHALL appear visually active and the "🇮🇳 हिन्दी" button SHALL appear inactive.

---

### Requirement 3: Tab Navigation

**User Story:** As a user, I want to navigate between 10 distinct topic sections via a navigation bar, so that I can find information quickly without scrolling through the entire document.

#### Acceptance Criteria

1. THE Dashboard SHALL display exactly 10 tabs in the navigation bar in this order: (1) Executive Dashboard, (2) Market & Financial Analytics, (3) Nutrient Master, (4) Farm Calendar, (5) Drip Irrigation Calculator, (6) Fertigation Schedules, (7) Crop Health & IPM, (8) Fruit Bagging & Diagnostics, (9) Procurement Calculator, (10) Critical Warnings.
2. WHEN a tab button is clicked, THE Dashboard SHALL display only that tab's content panel and hide all others, without a page reload.
3. WHEN a tab becomes active, THE Dashboard SHALL apply a distinct visual active state to that tab button (filled background, accent underline).
4. WHEN the page first loads, THE Dashboard SHALL display Tab 1 (Executive Dashboard) as the default active tab.
5. WHILE a tab is inactive, THE Dashboard SHALL not render or execute chart initialisation for that tab's charts, to avoid blank canvas errors.
6. THE navigation bar SHALL be horizontally scrollable on mobile viewports without wrapping to multiple lines.

---

### Requirement 4: Executive Dashboard Tab

**User Story:** As an orchard manager, I want an at-a-glance executive overview, so that I can quickly assess the orchard's operational status and key financial targets.

#### Acceptance Criteria

1. THE Executive_Dashboard SHALL display a 6-cell KPI grid containing: total tree count (2,100), current tree age (8 months), soil type (Vertisol), designated bahar (Mrig Bahar), target price range (₹60–₹85/kg 🔴), and mature net base case (~₹30 Lakhs/Yr 🔴).
2. THE Executive_Dashboard SHALL display 4 financial highlight cards: estimated Year 2 first revenue, mature gross revenue base case, estimated payback period, and bagging premium range — each carrying a 🔴 scenario label.
3. THE Executive_Dashboard SHALL display a phenological progress bar showing 4 orchard lifecycle phases: Months 8–12 (Framework), 13–15 (Ambe Removal), 16–17 (Bahar Stress), 18–24 (First Harvest).
4. THE Executive_Dashboard SHALL display an immediate directives panel listing the 4 month-8 operational actions: 100% manual deblossoming, 3-tier canopy training, surface drainage furrows, biological rootzone inoculation.
5. THE Executive_Dashboard SHALL render a bar chart of daily water volume (L/plant/day) per growth stage and a doughnut chart of Year-2 N-P-K ratio using Chart.js.
6. WHEN the Executive_Dashboard tab is activated, THE charts SHALL initialise only once (subsequent activations SHALL NOT re-create chart instances).

---

### Requirement 5: Market & Financial Analytics Tab

**User Story:** As a commercial farmer, I want to simulate different price and yield scenarios with a live financial calculator, so that I can make informed decisions about buyer channel strategy.

#### Acceptance Criteria

1. THE Financial_Simulator SHALL contain 4 interactive range sliders: average price realisation (₹35–₹120/kg, default ₹60), Year-2 yield (10–30 kg/tree, default 18), mature yield Year 4+ (25–65 kg/tree, default 30), and bagging & packing cost (₹1.50–₹5.00/fruit, default ₹2.75).
2. WHEN any slider value changes, THE Financial_Simulator SHALL immediately recompute and display: Year-2 gross revenue, Year-2 net income (gross minus OPEX of ₹4.2 L base plus per-fruit bagging cost), Year-4+ gross revenue, Year-4+ net income (gross minus OPEX of ₹7.5 L base plus per-fruit bagging cost).
3. THE Financial_Simulator SHALL assume 2,100 trees and 400 g average fruit weight for all calculations; these values SHALL NOT be hardcoded as magic numbers in UI rendering code but SHALL be defined as named constants.
4. THE Market_Tab SHALL display a static scenario range table with 6 yield rows (Downside 20 kg to Upside 48 kg) and 5 price columns (₹40, ₹50, ₹60, ₹70, ₹85) showing gross revenue only, with a footnote distinguishing gross from net.
5. THE Market_Tab SHALL render three Chart.js charts: (a) seasonal wholesale price trend (generic unbagged vs. Taiwan Pink bagged), (b) 4-year cumulative cashflow trajectory, (c) grade-wise revenue share doughnut.
6. ALL financial outputs and projections SHALL be labelled with "🔴 Scenario only — not a guaranteed forecast."
7. IF Year-2 or Year-4+ computed net income is negative, THEN THE Financial_Simulator SHALL display it in red text prefixed with "−₹".

---

### Requirement 6: Nutrient Master Tab

**User Story:** As an agronomist, I want to view detailed profiles for all 14 nutrients and biostimulants with evidence-graded dosage recommendations, so that I can calibrate the fertigation schedule against actual soil and leaf test results.

#### Acceptance Criteria

1. THE Nutrient_Master_Tab SHALL display Nutrient_Cards for all 14 entries: N, P, K, Ca, Mg, S, Zn, B, Fe, Mn, Cu, Mo, Humic/Fulvic Acid, Biofertilizers.
2. THE Nutrient_Master_Tab SHALL provide 5 filter buttons: All, Primary (N/P/K), Secondary (Ca/Mg/S), Micronutrients (Zn/B/Fe/Mn/Cu/Mo), Biostimulants.
3. WHEN a filter button is clicked, THE Nutrient_Master_Tab SHALL display only Nutrient_Cards belonging to that category; all others SHALL be hidden.
4. EACH Nutrient_Card SHALL display: symbol, full name, physiological role, yield/quality impact, visual deficiency symptoms, toxicity/excess risk, drip fertigation dose, foliar dose, basal/soil dose, Vertisol dynamics, and antagonism notes.
5. EACH dosage statement on a Nutrient_Card SHALL carry an Evidence_Grade badge (🟢A, 🔵B, 🟡C, or 🔴E).
6. IF a dosage recommendation has not been validated in published research for this specific cultivar or soil type, THEN the Nutrient_Card SHALL carry a 🟡C badge and a note that calibration via soil/leaf analysis is required.
7. THE Nutrient_Master_Tab SHALL display a legend explaining the Evidence_Grade scale.
8. EACH Nutrient_Card image SHALL be labelled "🔴 Illustrative only — not a deficiency photograph."

---

### Requirement 7: Farm Calendar Tab

**User Story:** As a farm manager, I want to browse month-by-month operational tasks from Month 8 through Month 20, so that I can plan field labour and input procurement week by week.

#### Acceptance Criteria

1. THE Farm_Calendar_Tab SHALL display 13 selectable month buttons labelled Month 8 through Month 20.
2. WHEN a month button is clicked, THE Farm_Calendar_Tab SHALL render a detail card for that month containing: phenology & focus, water target, weekly fertigation targets, foliar spray, canopy & pruning tasks, and IPM scouting tasks.
3. WHEN the Farm_Calendar_Tab first loads, THE Month 8 button SHALL be selected by default.
4. THE water target in each month's detail card SHALL include the formula inputs (ET₀×Kc×Kr÷η) as a tooltip or sub-label so the user can verify the calculation.
5. WHEN Month 16 (Drought Stress) is selected, THE water target SHALL prominently display "SHUT OFF DRIP COMPLETELY" in red text.

---

### Requirement 8: Drip Irrigation Calculator Tab

**User Story:** As an irrigation manager, I want to compute the daily water requirement per plant given my local evapotranspiration, crop stage, and drip hardware, so that I can schedule pump run-times accurately.

#### Acceptance Criteria

1. THE Drip_Irrigation_Calculator SHALL accept 3 user inputs: growth stage (dropdown of 9 stages with pre-filled ET₀ and Kc values), drip hardware configuration (2 drippers × 4 L/h or 4 drippers × 4 L/h), and system efficiency η (numeric input, default 0.90).
2. WHEN any input changes, THE Drip_Irrigation_Calculator SHALL immediately recompute and display: daily volume per plant (L/day), system run time (hours and minutes), and total orchard daily volume for 2,100 trees.
3. THE formula used SHALL be: V = ET₀ × Kc × Kr × S ÷ η, where S is the area per plant in m² (3.0 × 2.0 = 6.0 m²), and the result SHALL be displayed alongside the formula for transparency.
4. THE Drip_Irrigation_Calculator SHALL render a Chart.js bar/line chart showing stage-wise orchard total water demand across all 9 growth stages.
5. THE Drip_Irrigation_Calculator tab SHALL display a Vertisol drip maintenance protocol panel covering: bi-weekly line flush, acid wash (with caveat that frequency depends on water test results, not a fixed schedule), and biofilm chlorination.

---

### Requirement 9: Fertigation Schedules Tab

**User Story:** As a farm operator, I want to see weekly WSF quantities per tree and for the full orchard, so that I can batch-prepare tank injections correctly without calculation errors.

#### Acceptance Criteria

1. THE Fertigation_Tab SHALL display an annual RDF targets panel listing per-tree N-P₂O₅-K₂O targets for Year 1, Year 2, Year 3, and Mature Year 4+, each with an Evidence_Grade badge.
2. THE Fertigation_Tab SHALL display a 3-tank compatibility protocol panel clearly stating which fertilizer grades belong in Tank A, Tank B, and Tank C, and the rule forbidding direct mixing of Calcium Nitrate with Phosphates or Sulfates in the same tank.
3. THE Fertigation_Tab SHALL display a Stage 1 WSF schedule table (Months 8–12, 16-week programme) showing per-plant per-week dose, per-100-trees per-week dose, orchard-wide (2,100-tree) per-week dose, and 16-week total for each of 5 fertilizer grades.
4. THE Stage 1 WSF table values SHALL be derived from named constants in `data.js`, NOT hardcoded inline in the HTML.
5. THE Fertigation_Tab SHALL carry a disclaimer that the mature NPK targets must be calibrated with soil test and leaf tissue analysis after Year 2.

---

### Requirement 10: Crop Health & IPM Tab

**User Story:** As a farm scout, I want to search for a pest or disease and get threshold, biocontrol, and chemical control information, so that I can intervene at the correct timing.

#### Acceptance Criteria

1. THE IPM_Tab SHALL display a free-text search input and a category filter (All / Insect Pests / Diseases).
2. WHEN text is entered in the search input, THE IPM_Tab SHALL filter visible IPM_Cards in real time (no submit button required) to those whose name, description, or chemical recommendation text matches the query.
3. WHEN a category is selected in the filter, THE IPM_Tab SHALL display only IPM_Cards matching that category.
4. THE IPM_Tab SHALL display IPM_Cards for at least 8 entries: Oriental Fruit Fly, Guava Mealybug, Shoot & Fruit Borer, Bark-Eating Caterpillar, Guava Wilt Complex, Anthracnose & Dieback, Fruit Canker, Stylar End Rot.
5. EACH IPM_Card SHALL display: pest/disease name, ETL (economic threshold level), biocontrol/physical measures, chemical recommendation with PHI (pre-harvest interval) where applicable, and a brief description.
6. THE IPM_Tab SHALL display a prominent regulatory disclaimer stating that all chemical recommendations require verification against current CIB&RC registration before application.
7. THE IPM_Tab SHALL display a Visual Disease Identification Gallery with at least 8 identification cards, each either showing a verified Creative Commons image or a text-based symptom diagram with fallback text if the image fails to load.
8. THE IPM_Tab SHALL display an FRAC/IRAC resistance rotation strategy panel listing 4 spray windows with alternating mode-of-action groups.

---

### Requirement 11: Fruit Bagging & Diagnostics Tab

**User Story:** As a post-harvest quality manager, I want to understand the 3-layer bagging system and look up soil and water quality remediation actions, so that I can protect fruit quality and maintain drip system health.

#### Acceptance Criteria

1. THE Bagging_Tab SHALL describe the 3-layer composite bagging system (EPE foam mesh inner, perforated LDPE middle, UV-reflective paper outer) and SHALL carry a 🟡C evidence badge with a note that local validation is required.
2. THE Bagging_Tab SHALL state the pre-bagging spray directive (Azoxystrobin + Neem Oil, 24 hours before bagging, fruits must be dry).
3. THE Diagnostic_Lookup SHALL provide a dropdown with at least 7 diagnostic parameters: Soil pH, Soil ECe, Organic Carbon, Available Phosphorus, Free CaCO₃, Irrigation Water RSC, Irrigation Water SAR.
4. WHEN a parameter is selected in the Diagnostic_Lookup dropdown, THE Diagnostic_Lookup SHALL immediately display the target range and the remedial protocol for that parameter.
5. THE RSC and SAR remedial protocol text SHALL include a caveat that acid injection dose and gypsum dose must be calculated from actual water chemistry analysis, not applied at a fixed rate.

---

### Requirement 12: Procurement Calculator Tab

**User Story:** As an input buyer, I want to scale fertilizer and supply quantities to any orchard size from 100 to 5,000 trees, so that I can generate a purchase order without manual arithmetic.

#### Acceptance Criteria

1. THE Procurement_Calculator SHALL display a range slider from 100 to 5,000 trees (step 100) defaulting to 2,100.
2. WHEN the slider value changes, THE Procurement_Calculator SHALL immediately recompute and display scaled quantities in 3 panels: (a) Fertilizers & WSF, (b) Micronutrients & Bio-Agents, (c) Hardware & Bagging Supplies.
3. THE base quantities for scaling SHALL be defined as named constants in `data.js` keyed to 2,100 trees; scaling SHALL apply a linear multiplier (actual trees ÷ 2100).
4. ALL quantity outputs SHALL include both weight/count and the number of commercial bags or packs required, rounding up to the nearest whole unit.

---

### Requirement 13: Critical Warnings Tab

**User Story:** As a new farm worker, I want a checklist of the most critical mistakes to avoid, so that I do not accidentally damage the trees or lose the crop.

#### Acceptance Criteria

1. THE Critical_Warnings_Tab SHALL display at least 9 warning cards, one for each of: premature cropping, Vertisol root-collar waterlogging, tractor rotovation near trunk, glyphosate herbicide drift, calcium–phosphate tank mixing, unperforated plastic bagging, bloom-period insecticide spray, caustic chemical deblossoming, unbuffered water stress re-irrigation.
2. EACH warning card SHALL use red/amber background colour to visually distinguish it from informational content.
3. THE warning about chemical deblossoming SHALL clarify that spraying Urea or NAA on trees under 12 months is the prohibited action, and that manual deblossoming is the recommended alternative.

---

### Requirement 14: Responsive Layout & Visual Identity

**User Story:** As a mobile user, I want the dashboard to be usable on a smartphone, so that I can check data while standing in the orchard.

#### Acceptance Criteria

1. THE Dashboard SHALL use the Tailwind CSS CDN (v3) for utility classes and SHALL define the custom colour palette (bg #FDFBF7, primary #1E3A2B, secondary #4A7C59, accent #E07A5F, dark #2B2D42) in the Tailwind config extension in `index.html`.
2. THE Dashboard SHALL use Chart.js CDN for all chart rendering.
3. THE Dashboard SHALL use Font Awesome CDN for iconography.
4. ON mobile viewports (width < 640px), THE Dashboard SHALL render KPI grids as 2-column layouts and nutrient card grids as single-column layouts.
5. ON desktop viewports (width ≥ 1024px), THE Dashboard SHALL render nutrient card grids as 3-column layouts.
6. THE navigation bar SHALL allow horizontal scrolling on viewports narrower than the total navigation width, without wrapping tabs onto a second line.
7. ALL chart canvases SHALL be wrapped in a container with `max-width: 650px` and `height: 320px` (260px on mobile) to prevent oversized rendering.

---

### Requirement 15: Data Integrity & Disclaimer Standards

**User Story:** As a reader who may make real investment decisions, I want every claim to carry a clear evidence grade and every financial projection to be labelled as a scenario, so that I am not misled by unqualified assertions.

#### Acceptance Criteria

1. EVERY agronomic dosage or yield claim in the Dashboard SHALL be annotated with exactly one of: 🟢A (NHB/ICAR official source), 🔵B (peer-reviewed research), 🟡C (local adaptation requiring validation), 🔴E (scenario/forecast only).
2. THE Dashboard SHALL NOT use absolute language such as "100% protection", "zero cracking", "guaranteed", or "always" in any user-visible text.
3. ALL financial projections in the Financial_Simulator and scenario table SHALL be prefixed or suffixed with "🔴 Scenario only."
4. THE Dashboard SHALL NOT display any village name, GPS coordinates, or other location identifiers more specific than "Badnawar Tehsil, Dhar District, Madhya Pradesh."
5. THE pesticide regulatory disclaimer SHALL appear in the IPM_Tab before the first IPM_Card and SHALL state that CIB&RC registration must be verified before applying any chemical.
6. WHEN displaying NPK targets, THE Dashboard SHALL include a note stating that mature targets must be adjusted after soil test and leaf tissue analysis, and SHALL reference the ICAR-IIHR high-density guava research finding of 340:70:260 g N:P₂O₅:K₂O as an alternative reference point.
