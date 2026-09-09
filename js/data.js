/**
 * data.js — Guava Dashboard Master Data File
 * Taiwan Pink Guava (Psidium guajava) — 2100-tree Vertisol Orchard
 *
 * All agronomic data is for decision-support only. Verify nutrient doses,
 * pesticide registrations (CIB&RC), and water requirements with local experts
 * before operational use. Evidence grades: 🟢A = strong, 🟡C = indicative.
 *
 * Tasks covered: 6 (Orchard constants), 7 (NUTRIENTS_DATA),
 *                8 (CALENDAR_DATA), 9 (IPM_DATA + FRAC_IRAC_ROTATION),
 *               10 (Market data)
 */

// ─────────────────────────────────────────────────────────────────────────────
// TASK 6 — ORCHARD CONSTANTS
// ─────────────────────────────────────────────────────────────────────────────

export const ORCHARD = {
  trees: 2100,
  avgFruitWeightKg: 0.400,
  spacingM2: 6.0
};

export const OPEX_BASE = {
  yr2: 420000,
  yr4: 750000
};

export const SCENARIO_YIELDS = [20, 25, 30, 35, 40, 48];

export const SCENARIO_PRICES = [40, 50, 60, 70, 85];

/**
 * IRRIGATION_STAGES — 9 phenological stages
 * et0: reference evapotranspiration (mm/day)
 * kc:  crop coefficient
 * kr:  canopy cover reduction factor
 * waterLpd computed as: et0 × kc × kr × spacingM2 ÷ 0.90
 */
export const IRRIGATION_STAGES = [
  { id: '8-10',   label: '8–10 Months (Post-Monsoon Establishment)',   et0: 4.2, kc: 0.45, kr: 0.26 },
  { id: '11-12',  label: '11–12 Months (Pre-Bloom Hardening)',          et0: 3.8, kc: 0.50, kr: 0.30 },
  { id: '13-14',  label: '13–14 Months (Bloom & Fruit Set)',            et0: 5.5, kc: 0.70, kr: 0.38 },
  { id: '15',     label: '15 Months (Fruit Development)',               et0: 6.0, kc: 0.80, kr: 0.45 },
  { id: '16',     label: '16 Months (Drought Stress / Pre-Harvest)',    et0: 5.8, kc: 0.30, kr: 0.50 },
  { id: '17',     label: '17 Months (Harvest)',                         et0: 5.5, kc: 0.75, kr: 0.52 },
  { id: '18-19',  label: '18–19 Months (Post-Harvest Recovery)',        et0: 4.8, kc: 0.60, kr: 0.55 },
  { id: '20',     label: '20 Months (Canopy Expansion)',                et0: 5.0, kc: 0.65, kr: 0.58 },
  { id: 'mature', label: 'Mature Tree (Year 4+)',                       et0: 5.5, kc: 0.85, kr: 0.70 }
];

// ─────────────────────────────────────────────────────────────────────────────
// TASK 7 — NUTRIENTS_DATA (14 entries)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * NUTRIENTS_DATA
 * imageLabel is always illustrative — never a real deficiency photograph.
 * Evidence grades reflect calibration status for Taiwan Pink on Vertisol.
 * No absolute claims (no "100% protection", "guaranteed", "always", "zero cracking").
 */
export const NUTRIENTS_DATA = [
  {
    id: 'n',
    symbol: 'N',
    name: 'Nitrogen',
    category: 'macro',
    role: 'Vegetative growth, chlorophyll synthesis, enzyme activation',
    impact: 'Critical for canopy establishment Months 8–12; excess delays fruit maturity',
    deficiency: 'Yellowing of older leaves, stunted growth, reduced shoot extension',
    excess: 'Lush vegetative growth, delayed flowering, increased aphid susceptibility',
    doseDrip: '200 g N/tree/yr in 8 split applications 🟢A',
    doseFoliar: '1–2% urea spray monthly 🟡C — calibrate on sample trees first',
    doseSoil: '100 g Urea/tree basal at establishment 🟢A',
    vertisol: 'High clay CEC fixes ammonium; prefer split fertigation over broadcast 🟡C',
    antagonism: 'Excess N suppresses Zn and B uptake; maintain N:K ≤1:1 during fruit fill',
    evidenceGrade: 'A',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'p',
    symbol: 'P',
    name: 'Phosphorus',
    category: 'macro',
    role: 'Root development, energy transfer (ATP), flowering initiation',
    impact: 'High Vertisol CaCO₃ fixes P rapidly; placement near root zone essential',
    deficiency: 'Dark green or purplish tinge on older leaves, poor root development, delayed maturity',
    excess: 'Induces Zn, Fe, Mn deficiency through antagonism; rare in field conditions',
    doseDrip: '50 g P₂O₅/tree/yr as MAP or MKP 🟢A',
    doseFoliar: '0.5% MAP spray at flowering 🟡C',
    doseSoil: '50 g DAP/tree at planting in root zone 🟢A',
    vertisol: 'Apply as banded placement; broadcast application wastes P in high-CaCO₃ Vertisols 🟡C — verify with Olsen P test',
    antagonism: 'Excess P locks out Zn, Fe, Mn; do not over-apply; Ca–P precipitation if mixed with Calcium Nitrate',
    evidenceGrade: 'A',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'k',
    symbol: 'K',
    name: 'Potassium',
    category: 'macro',
    role: 'Fruit size, sugar loading, stomatal regulation, drought tolerance',
    impact: 'Most important nutrient during fruit development (Months 13–17); governs Brix and shelf life',
    deficiency: 'Scorching of leaf margins on older leaves, small fruit, poor colour development',
    excess: 'Antagonises Ca and Mg; causes bitter pit-like disorders in some cultivars',
    doseDrip: '260 g K₂O/tree/yr in 6–8 splits; increase to 340 g during fruit fill 🟢A',
    doseFoliar: '0.5–1% KNO₃ spray at fruit set 🟡C',
    doseSoil: 'MOP 50 g/tree basal pre-monsoon 🟡C — leaching risk in Vertisol furrows',
    vertisol: 'Vertisol K-fixation moderate; drip delivery preferred; monitor with petiole analysis 🟡C',
    antagonism: 'Excess K suppresses Ca and Mg; K:Ca:Mg ratio target ~5:3:1 in leaf tissue',
    evidenceGrade: 'A',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'ca',
    symbol: 'Ca',
    name: 'Calcium',
    category: 'secondary',
    role: 'Cell wall integrity, fruit firmness, tip-burn prevention',
    impact: 'Low Ca leads to fruit cracking and poor post-harvest shelf life',
    deficiency: 'Tip-burn of young leaves, blossom-end breakdown, fruit cracking',
    excess: 'Rarely toxic; excessive lime raises pH and locks out micronutrients',
    doseDrip: '150 g CaO/tree/yr as Calcium Nitrate 🟡C — local validation required',
    doseFoliar: '0.5% CaCl₂ spray at fruitlet stage, 2–3 applications 🟡C',
    doseSoil: 'Gypsum 200 g/tree if ECe < 0.8 dS/m and Ca deficient 🟡C',
    vertisol: 'Vertisols typically high in Ca; deficiency rare but occurs when K/Mg ratio is elevated; verify with leaf tissue analysis 🟡C — calibration required',
    antagonism: 'Never mix Calcium Nitrate with phosphates or sulfates in same tank — precipitate forms',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'mg',
    symbol: 'Mg',
    name: 'Magnesium',
    category: 'secondary',
    role: 'Chlorophyll centre, enzyme co-factor, phloem sugar loading',
    impact: 'Inter-veinal chlorosis reduces photosynthetic capacity and fruit sugar content',
    deficiency: 'Inter-veinal chlorosis on older leaves, premature leaf drop, reduced fruit Brix',
    excess: 'Antagonises K and Ca; rare under normal fertigation',
    doseDrip: '40 g MgO/tree/yr as Magnesium Sulphate 🟡C — calibrate after leaf analysis',
    doseFoliar: '0.5% MgSO₄ spray monthly during fruiting 🟡C',
    doseSoil: 'Kieserite 50 g/tree if Mg < 0.5 cmol/kg in soil test 🟡C',
    vertisol: 'Vertisol Mg often adequate; deficiency appears when K over-applied; K:Mg > 5:1 triggers deficiency 🟡C — calibration required for this cultivar',
    antagonism: 'K excess most common cause of Mg deficiency; balance fertigations',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 's',
    symbol: 'S',
    name: 'Sulphur',
    category: 'secondary',
    role: 'Amino acid synthesis (methionine, cysteine), flavour compound precursors',
    impact: 'Deficiency reduces fruit aroma and protein synthesis in young shoots',
    deficiency: 'Yellowing of young leaves (unlike N which affects older leaves), stunted young shoots',
    excess: 'Acidification of drip zone in calcareous Vertisols; monitor pH quarterly',
    doseDrip: '20 g S/tree/yr via sulfate-form fertilizers 🟡C',
    doseFoliar: 'Wettable sulphur 0.2% for dual fungicide + nutrition role 🟡C',
    doseSoil: 'Included via gypsum or MgSO₄ applications 🟡C',
    vertisol: 'Calcareous Vertisols buffer S; sulfate leaches less than in sandy soils 🟡C — calibration required',
    antagonism: 'Sulfate-form fertilizers must NOT be mixed with Calcium Nitrate (precipitate)',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'zn',
    symbol: 'Zn',
    name: 'Zinc',
    category: 'micro',
    role: 'Auxin synthesis, enzyme activation, pollen viability',
    impact: 'Little leaf syndrome reduces canopy; critical for fruit set and seed development',
    deficiency: 'Little leaf (small bunched leaves), shortened internodes, mottled young leaves',
    excess: 'Phytotoxic at high doses; rare under recommended rates',
    doseDrip: '5 g Zn/tree/yr as Zinc EDTA chelate 🟡C — calibrate with leaf analysis',
    doseFoliar: '0.5% ZnSO₄ + 0.25% lime spray at flush 🟡C',
    doseSoil: 'ZnSO₄ 25 g/tree banded in root zone 🟡C',
    vertisol: 'High pH Vertisols strongly fix Zn; chelated form preferred; verify with DTPA-Zn soil test 🟡C — calibration required for Taiwan Pink cultivar',
    antagonism: 'P excess strongly antagonises Zn; keep P applications minimal and banded',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'b',
    symbol: 'B',
    name: 'Boron',
    category: 'micro',
    role: 'Pollen tube germination, fruit set, cell wall pectin cross-linking',
    impact: 'Deficiency causes fruit cracking and hollow heart; critical at bloom stage',
    deficiency: 'Distorted young leaves, corky lesions on fruit, poor fruit set, hollow heart',
    excess: 'Toxic narrow margin; stay within recommended range; do not exceed 2 g/L foliar',
    doseDrip: '1–2 g B/tree/yr as Borax or Solubor 🟡C — narrow toxicity margin, calibrate carefully',
    doseFoliar: '0.1–0.2% Borax spray at pink bud and fruit set 🟡C',
    doseSoil: 'Borax 5 g/tree banded 🟡C — avoid broadcast in calcareous soil',
    vertisol: 'Calcareous Vertisols reduce B availability; foliar application more reliable than soil 🟡C — calibration required for Taiwan Pink cultivar',
    antagonism: 'Ca and B are synergistic; adequate Ca improves B utilisation',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'fe',
    symbol: 'Fe',
    name: 'Iron',
    category: 'micro',
    role: 'Chlorophyll synthesis, electron transport, enzyme activation',
    impact: 'Lime-induced chlorosis is common on high-CaCO₃ Vertisols; reduces photosynthesis',
    deficiency: 'Inter-veinal chlorosis on young leaves (green veins, yellow tissue), in severe cases leaves turn white',
    excess: 'Rarely toxic under normal soil conditions',
    doseDrip: '5–10 g Fe/tree/yr as Fe-EDDHA chelate 🟡C — chelate form essential in calcareous soils',
    doseFoliar: '0.2% FeSO₄ + 0.1% citric acid spray 🟡C',
    doseSoil: 'Fe-EDDHA 10 g/tree banded in root zone 🟡C',
    vertisol: 'High CaCO₃ in Vertisols strongly precipitates Fe; EDDHA chelate is most stable at high pH; verify with DTPA-Fe soil test 🟡C — calibration required',
    antagonism: 'P and Ca excess reduce Fe availability; Cu and Mn compete at uptake sites',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'mn',
    symbol: 'Mn',
    name: 'Manganese',
    category: 'micro',
    role: 'Photosystem II, nitrogen metabolism, enzyme activation',
    impact: 'Deficiency reduces photosynthetic efficiency; important during rapid canopy growth',
    deficiency: 'Inter-veinal chlorosis on young to middle-aged leaves, grey speck on grains of associated crops',
    excess: 'Toxicity at pH < 5.5; not a risk in calcareous Vertisols',
    doseDrip: '2–4 g Mn/tree/yr as MnSO₄ or Mn chelate 🟡C',
    doseFoliar: '0.3% MnSO₄ spray at canopy flush 🟡C',
    doseSoil: 'MnSO₄ 15 g/tree banded 🟡C',
    vertisol: 'High pH Vertisols reduce Mn availability; foliar supplementation often more reliable 🟡C — calibration required for this cultivar',
    antagonism: 'Fe, Zn, Cu compete with Mn at uptake; balanced micronutrient programme reduces antagonism',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'cu',
    symbol: 'Cu',
    name: 'Copper',
    category: 'micro',
    role: 'Lignin synthesis, enzyme activation, disease resistance signalling',
    impact: 'Deficiency weakens shoot tips; copper also has fungicidal properties at foliar doses',
    deficiency: 'Wilting and die-back of young shoot tips, blue-green colour loss in leaves',
    excess: 'Toxic accumulation in soil with repeated Bordeaux mixture use; monitor soil Cu',
    doseDrip: '1–2 g Cu/tree/yr as CuSO₄ or Cu chelate 🟡C',
    doseFoliar: '0.2% CuSO₄ + lime (Bordeaux) at 3-week intervals during humid period 🟡C — verify CIB&RC registration before application',
    doseSoil: 'CuSO₄ 10 g/tree banded 🟡C — monitor cumulative soil Cu levels',
    vertisol: 'Vertisol organic matter binds Cu; deficiency more likely in low-OM soils; calibration required 🟡C',
    antagonism: 'Excess Cu antagonises Fe, Zn, Mo; avoid over-application',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'mo',
    symbol: 'Mo',
    name: 'Molybdenum',
    category: 'micro',
    role: 'Nitrate reductase, nitrogen fixation (in biofertilizer context)',
    impact: 'Deficiency rare but can appear as marginal scorch on young leaves; important for legume cover crops',
    deficiency: 'Marginal and tip scorch on young leaves, whiptail in severe cases',
    excess: 'Toxicity very rare; Mo is needed in trace amounts only',
    doseDrip: '0.1 g Mo/tree/yr as sodium or ammonium molybdate 🟡C',
    doseFoliar: '0.02% ammonium molybdate spray once per season 🟡C',
    doseSoil: 'Apply with micronutrient mix 🟡C',
    vertisol: 'Mo availability increases with pH; calcareous Vertisols may have adequate Mo; soil test before applying 🟡C — calibration required',
    antagonism: 'Sulfate reduces Mo uptake; keep S applications moderate',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'ha',
    symbol: 'HA',
    name: 'Humic & Fulvic Acid',
    category: 'bio',
    role: 'Soil structure improvement, chelation of micronutrients, root proliferation stimulation',
    impact: 'Improves CEC in Vertisols, enhances water retention and nutrient availability',
    deficiency: 'Not a plant nutrient deficiency; low organic matter reduces soil biology',
    excess: 'No known toxicity at recommended rates',
    doseDrip: '2–5 kg humic acid granules/tree/yr via drip 🟡C — local validation required',
    doseFoliar: '0.1% fulvic acid spray at transplanting and post-pruning 🟡C',
    doseSoil: 'Humic acid granules 100 g/tree incorporated in root zone at planting 🟡C',
    vertisol: 'Vertisols have naturally high clay but may be low in stable humus; humic applications improve aggregate stability 🟡C — calibration required',
    antagonism: 'Humic acids chelate micronutrients and may reduce availability if applied in excess with micronutrients',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  },
  {
    id: 'bio',
    symbol: 'BIO',
    name: 'Biofertilizers',
    category: 'bio',
    role: 'Biological N-fixation (Azotobacter), P-solubilisation (PSB), mycorrhizal root extension',
    impact: 'Can reduce chemical fertiliser requirement by 15–25% over time; improves root health 🟡C — local field validation required before reducing chemical inputs',
    deficiency: 'Not a deficiency concept; low soil microbial activity reduces nutrient cycling efficiency',
    excess: 'No known toxicity; over-inoculation rarely persists in field conditions',
    doseDrip: 'PSB 500 g/200L water applied quarterly via drip 🟡C',
    doseFoliar: 'Not applicable for most biofertilizers',
    doseSoil: 'Rhizobium + PSB + Trichoderma viride seed/root dip at transplanting 🟡C',
    vertisol: 'Vertisol pH 7.5–8.5 may suppress some microbial strains; select alkali-tolerant strains; biological activity decreases during soil cracking events 🟡C — calibration required',
    antagonism: 'Do not apply biofertilizers with chemical fungicides or high-salinity fertiliser solutions simultaneously',
    evidenceGrade: 'C',
    imageLabel: '🔴 Illustrative only — not a deficiency photograph.'
  }
];

// ─────────────────────────────────────────────────────────────────────────────
// TASK 8 — CALENDAR_DATA (months 8–20, 13 entries)
// waterLpd = ET₀ × Kc × Kr × 6.0 ÷ 0.90  (rounded to 2 decimal places)
// Month 16: droughtStop = true, waterLpd = 0 (deliberate)
// ─────────────────────────────────────────────────────────────────────────────

export const CALENDAR_DATA = [
  {
    month: 8,
    title: 'Month 8 — Vegetative Framework',
    pheno: 'Rapid vegetative growth; root establishment; canopy training phase',
    waterLpd: 3.28,
    waterFormula: 'ET₀(4.2) × Kc(0.45) × Kr(0.26) × 6m² ÷ 0.90',
    fert: 'Rhizobium + PSB inoculation at root zone. Begin WSF Stage 1: 19-19-19 @ 5g/tree/week via drip',
    foliar: 'Humic acid 0.1% + Zinc EDTA 0.2% spray to establish foliar uptake',
    pruning: 'Train single main stem to 60cm; remove lateral shoots below scaffold branches; remove all flowers immediately (deblossoming)',
    ipm: 'Scout for shoot borer weekly; apply Beauveria bassiana as prophylactic soil drench; check for mealybug on stem base',
    droughtStop: false
  },
  {
    month: 9,
    title: 'Month 9 — Root & Shoot Extension',
    pheno: 'Secondary root flush; lateral branch initiation; post-monsoon soil moisture receding',
    waterLpd: 3.28,
    waterFormula: 'ET₀(4.2) × Kc(0.45) × Kr(0.26) × 6m² ÷ 0.90',
    fert: 'Continue WSF 19-19-19 @ 7g/tree/week; add Calcium Nitrate 2g/tree/week in Tank A',
    foliar: 'Borax 0.1% + MgSO₄ 0.3% spray for micronutrient support',
    pruning: 'Select 3–4 primary scaffold branches; remove inward-growing shoots; maintain open centre',
    ipm: 'Fruit fly bait stations install (1 per 10 trees); check mealybug; apply neem oil 2mL/L if shoot borer infestation > ETL',
    droughtStop: false
  },
  {
    month: 10,
    title: 'Month 10 — Canopy Consolidation',
    pheno: 'Scaffold branches hardening; canopy cover ~20%; drainage furrows critical before winter rain',
    waterLpd: 3.28,
    waterFormula: 'ET₀(4.2) × Kc(0.45) × Kr(0.26) × 6m² ÷ 0.90',
    fert: 'Transition to higher K ratio: 12-6-20 WSF @ 8g/tree/week; introduce Fe-EDDHA 1g/tree/week',
    foliar: '0.5% KNO₃ foliar for K loading; Fe chelate 0.2% if inter-veinal chlorosis observed',
    pruning: 'Excavate drainage furrows between rows to prevent waterlogging at root collar',
    ipm: 'Bark-eating caterpillar inspection; clear weeds from tree base (alternate host removal); Trichoderma soil application',
    droughtStop: false
  },
  {
    month: 11,
    title: 'Month 11 — Pre-Bloom Hardening',
    pheno: 'Vegetative growth slowing; initiation of floral bud differentiation under mild stress',
    waterLpd: 3.80,
    waterFormula: 'ET₀(3.8) × Kc(0.50) × Kr(0.30) × 6m² ÷ 0.90',
    fert: 'Reduce N, increase K: 8-8-32 WSF @ 8g/tree/week; continue Ca nitrate 3g/tree/week',
    foliar: 'Boron 0.1% spray at bud initiation; Zn EDTA 0.2%',
    pruning: 'Final canopy shaping; remove crossing branches; tip-prune long shoots to encourage lateral buds',
    ipm: 'Anthracnose monitoring on leaf tips; prophylactic copper oxychloride 0.3% spray — verify CIB&RC registration before application',
    droughtStop: false
  },
  {
    month: 12,
    title: 'Month 12 — Flower Bud Formation',
    pheno: 'Flower buds visible on new flush; critical period for Zn and B adequacy',
    waterLpd: 3.80,
    waterFormula: 'ET₀(3.8) × Kc(0.50) × Kr(0.30) × 6m² ÷ 0.90',
    fert: 'High P + K: MKP 5g + SOP 5g/tree/week; stop N drip fertigations temporarily to harden tissue',
    foliar: '0.2% Borax + 0.1% ZnSO₄ + 0.05% MnSO₄ pre-bloom spray',
    pruning: 'Minimal pruning at bud stage; avoid disturbing flower buds',
    ipm: 'Fruit fly trap monitoring; Beauveria bassiana spray for prophylaxis; mealybug check',
    droughtStop: false
  },
  {
    month: 13,
    title: 'Month 13 — Anthesis & Fruit Set',
    pheno: 'Full bloom; pollination; fruitlet formation; highest water demand begins',
    waterLpd: 9.73,
    waterFormula: 'ET₀(5.5) × Kc(0.70) × Kr(0.38) × 6m² ÷ 0.90',
    fert: 'Resume N + Ca: Calcium Nitrate 5g/tree/week in Tank A; MKP 3g/tree/week in Tank B',
    foliar: '0.5% CaCl₂ spray at fruitlet (5mm) stage; 0.1% Borax at petal fall',
    pruning: 'Remove non-fruiting blind shoots; maintain light penetration to fruit clusters',
    ipm: 'AVOID insecticides during full bloom — protects pollinators; use only sticky traps; begin Oriental Fruit Fly mass trapping',
    droughtStop: false
  },
  {
    month: 14,
    title: 'Month 14 — Cell Division & Fruit Sizing',
    pheno: 'Rapid cell division in fruitlets; fruit sizing begins; K demand increases sharply',
    waterLpd: 9.73,
    waterFormula: 'ET₀(5.5) × Kc(0.70) × Kr(0.38) × 6m² ÷ 0.90',
    fert: 'Increase K to 340g K₂O/tree/yr equivalent: SOP 8g/tree/week; Ca nitrate 4g/tree/week; Mg sulphate 2g/tree/week',
    foliar: '0.5% KNO₃ + 0.3% CaCl₂ weekly spray; Fe chelate if chlorosis observed',
    pruning: 'Fruit thinning if cluster load > 3 fruits/branch-tip; retain 2 per cluster for size',
    ipm: 'Fruit fly damage monitoring; Spinosad bait spray — verify CIB&RC registration before application; mealybug contact spray if ETL exceeded',
    droughtStop: false
  },
  {
    month: 15,
    title: 'Month 15 — Fruit Development & Bagging',
    pheno: 'Fruit at 60–80mm size; bagging window (fruit dry, disease-free); highest single-month water demand',
    waterLpd: 14.40,
    waterFormula: 'ET₀(6.0) × Kc(0.80) × Kr(0.45) × 6m² ÷ 0.90',
    fert: 'Full K loading: SOP 10g/tree/week; reduce N to maintain low-N pre-harvest; Ca nitrate 3g/tree/week',
    foliar: 'Pre-bagging spray: Azoxystrobin 0.1% + Neem oil 2mL/L; apply 24h before bagging — verify CIB&RC registration before application',
    pruning: 'No pruning during fruit development; remove diseased or damaged fruitlets only',
    ipm: 'Complete bagging of all fruit within 1 week; maintain fruit fly bait traps; inspect for stylar end rot pre-bagging',
    droughtStop: false
  },
  {
    month: 16,
    title: 'Month 16 — Drought Stress (Pre-Harvest)',
    pheno: 'Deliberate water stress to synchronise maturation and intensify sugar loading',
    waterLpd: 0,
    waterFormula: 'SHUT OFF DRIP COMPLETELY — Drought stress to initiate uniform flowering',
    fert: 'No fertigation during drought period; K already loaded in fruit',
    foliar: 'No foliar spray during stress period; avoid disturbing stress signal',
    pruning: 'No pruning; monitor for fruit drop',
    ipm: 'Continue to monitor bagged fruit; check bags for mechanical damage or pest entry',
    droughtStop: true
  },
  {
    month: 17,
    title: 'Month 17 — Harvest',
    pheno: 'Fruit maturity (85–90 days from fruit set); harvest at firm-mature stage for market transport',
    waterLpd: 14.27,
    waterFormula: 'ET₀(5.5) × Kc(0.75) × Kr(0.52) × 6m² ÷ 0.90',
    fert: 'Resume drip at harvest; post-harvest K top-up: SOP 5g/tree/week for 2 weeks',
    foliar: 'Post-harvest: Zinc EDTA 0.3% + Boron 0.1% to replenish reserves',
    pruning: 'Harvest pruning: remove fruited wood immediately after picking; head back main branches by 30–40%',
    ipm: 'Post-harvest sanitation: remove all fallen fruit; burn diseased material; apply Trichoderma to pruning wounds',
    droughtStop: false
  },
  {
    month: 18,
    title: 'Month 18 — Post-Harvest Recovery',
    pheno: 'New flush emerging from pruned stubs; nutrient recovery phase; root regeneration',
    waterLpd: 10.56,
    waterFormula: 'ET₀(4.8) × Kc(0.60) × Kr(0.55) × 6m² ÷ 0.90',
    fert: 'Recovery programme: 19-19-19 WSF 10g/tree/week; humic acid 2g/tree/week; PSB re-inoculation',
    foliar: 'Full micronutrient cocktail: Zn + B + Fe + Mn + Mg spray at first flush',
    pruning: 'Second-round framework pruning: select fruiting laterals for next cycle; remove weak growth',
    ipm: 'Shoot borer monitoring on new flush; Beauveria bassiana preventive application; mealybug crawlers on new growth',
    droughtStop: false
  },
  {
    month: 19,
    title: 'Month 19 — Second Cycle Establishment',
    pheno: 'Canopy rebuilding; lateral shoot extension; orchard entering second production cycle',
    waterLpd: 10.56,
    waterFormula: 'ET₀(4.8) × Kc(0.60) × Kr(0.55) × 6m² ÷ 0.90',
    fert: 'Mature NPK programme begins: N 340g, P₂O₅ 70g, K₂O 260g per tree per year (ICAR-IIHR reference) split over 8 applications 🟢A — calibrate with soil/leaf analysis',
    foliar: 'Borax 0.1% + Ca chelate 0.3% spray at flower bud initiation',
    pruning: 'Train new scaffold laterals; maintain 3–4 primary branches per tree; remove water sprouts',
    ipm: 'Guava wilt complex monitoring — inspect root collar; remove and destroy any wilt-affected trees; disinfect tools with 70% ethanol',
    droughtStop: false
  },
  {
    month: 20,
    title: 'Month 20 — Canopy Expansion (Mature Cycle)',
    pheno: 'Full second-cycle canopy; approaching first commercial-scale harvest season',
    waterLpd: 12.57,
    waterFormula: 'ET₀(5.0) × Kc(0.65) × Kr(0.58) × 6m² ÷ 0.90',
    fert: 'Continue mature NPK; increase K₂O to 340g in fruit fill phase; Ca nitrate 150g CaO equivalent per tree',
    foliar: 'Pre-bloom: Boron 0.15% + Zinc 0.3% + Manganese 0.2% combined spray',
    pruning: 'Inter-canopy thinning to maintain 40% light penetration; remove dead wood and crossing branches',
    ipm: 'Full IPM calendar: fruit fly traps active; Anthracnose prophylaxis with FRAC-group rotation; Mealybug biological control (Cryptolaemus release if available)',
    droughtStop: false
  }
];

// ─────────────────────────────────────────────────────────────────────────────
// TASK 9 — IPM_DATA and FRAC_IRAC_ROTATION
// ─────────────────────────────────────────────────────────────────────────────

export const IPM_DATA = [
  {
    id: 'off',
    category: 'insect',
    name: 'Oriental Fruit Fly (Bactrocera dorsalis)',
    etl: '1 fly per trap per day triggers intervention',
    bio: 'Mass trapping with methyl eugenol + malathion bait stations (1 per 10 trees); Spinosad bait (GF-120 type) on foliage; encourage parasitoid wasps by reducing broad-spectrum sprays',
    chem: 'Spinosad 45 SC @ 0.5 mL/L bait spray on foliage edge — verify CIB&RC registration before application. PHI: 3 days',
    desc: 'Most damaging pest of guava post fruit set; female lays eggs under fruit skin; maggots destroy fruit interior; bagged fruit provides strong physical barrier',
    fallbackSymptoms: [
      'Pin-prick entry holes on fruit surface with oozing fluid',
      'Premature fruit drop with internal decay',
      'Maggots visible when cut fruit is sliced',
      'Fermented odour from affected fruits',
      'Yellow discolouration around oviposition site'
    ]
  },
  {
    id: 'gmb',
    category: 'insect',
    name: 'Guava Mealybug (Ferrisia virgata / Maconellicoccus hirsutus)',
    etl: '> 10% shoots infested or visible sooty mould formation',
    bio: 'Cryptolaemus montrouzieri (mealybug destroyer) release @ 10 per tree; Beauveria bassiana 1×10⁸ cfu/mL spray; remove ant colonies that protect mealybugs',
    chem: 'Imidacloprid 17.8 SL @ 0.5 mL/L stem drench or Chlorpyrifos 20 EC @ 2 mL/L spray — verify CIB&RC registration before application. PHI: 21 days',
    desc: 'White waxy insects colonise stem crotches and fruit stalk; excretes honeydew causing sooty mould; vectors pink disease; severe infestation stunts new growth',
    fallbackSymptoms: [
      'White waxy cottony masses on stem junctions and leaf undersides',
      'Sticky honeydew deposits on leaves below infestation',
      'Black sooty mould coating on leaves and stems',
      'Stunted new shoot growth near heavily infested areas',
      'Ant trails up and down the trunk tending mealybug colonies'
    ]
  },
  {
    id: 'sfb',
    category: 'insect',
    name: 'Shoot & Fruit Borer (Deudorix isocrates)',
    etl: '> 5% shoot tips wilted or 2% fruit with entry holes',
    bio: 'Trichogramma chilonis egg parasitoid cards (50,000 eggs/card) per acre; NPV (Nuclear Polyhedrosis Virus) spray; remove and destroy infested shoot tips weekly',
    chem: 'Chlorantraniliprole 18.5 SC @ 0.4 mL/L spray — verify CIB&RC registration before application. PHI: 7 days',
    desc: 'Larva bores into tender shoot tips causing "dead heart" wilting; later bores into young fruit; adult is a small moth; continuous scouting critical',
    fallbackSymptoms: [
      'Wilted and dead shoot tips ("dead heart") with entry hole at base',
      'Small circular entry holes on young developing fruit',
      'Frass (caterpillar droppings) around bored entry holes',
      'Premature fruit drop of bored fruit',
      'Larva visible inside split-open affected shoot or fruit'
    ]
  },
  {
    id: 'bec',
    category: 'insect',
    name: 'Bark-Eating Caterpillar (Indarbela tetraonis)',
    etl: 'Any bark damage > 10 cm diameter warrants immediate treatment',
    bio: 'Entomopathogenic nematodes (Steinernema carpocapsae) injected into galleries; swabbing with neem oil 10% into bored holes',
    chem: 'Inject Chlorpyrifos 20 EC (2 mL/L) or Dichlorvos 76 EC (5 mL/L) into galleries and seal with mud — verify CIB&RC registration before application',
    desc: 'Larva constructs silken galleries on bark and bores into wood; weakens structural integrity of main branches; common on 2–5 year old trees; detected by webbing on bark',
    fallbackSymptoms: [
      'Silken webs mixed with bark frass plastered on main trunk/branches',
      'Irregular bark damage underneath webbing',
      'Entry holes into wood beneath gallery',
      'Sap oozing from bark wounds',
      'Weakened branch structure with internal tunnels'
    ]
  },
  {
    id: 'gwc',
    category: 'disease',
    name: 'Guava Wilt Complex (Fusarium oxysporum f.sp. psidii + Meloidogyne spp.)',
    etl: 'Any confirmed wilt case requires immediate removal of affected tree',
    bio: 'Trichoderma viride 1×10⁸ cfu/g @ 50g/tree drench quarterly; Pseudomonas fluorescens 1×10⁸ cfu/mL drench; maintain soil organic matter > 1%',
    chem: 'No curative chemical control available; preventive Carbendazim 50 WP (0.1%) root drench in newly affected areas — verify CIB&RC registration before application',
    desc: 'Most serious disease of guava; Fusarium infection aided by root-knot nematode damage; causes yellowing, wilting, defoliation and tree death within 1–3 months; infected trees must be removed and destroyed',
    fallbackSymptoms: [
      'Sudden yellowing and wilting of leaves starting from one branch',
      'Progressive wilting spreading to whole canopy over 2–6 weeks',
      'Reddish-brown vascular discolouration when stem is cut',
      'Root-knot galls on roots when excavated',
      'Tree death within months of symptom appearance'
    ]
  },
  {
    id: 'adb',
    category: 'disease',
    name: 'Anthracnose & Dieback (Colletotrichum gloeosporioides)',
    etl: '> 5% of new shoots showing tip dieback or > 10% fruit surface affected',
    bio: 'Trichoderma asperellum spray at flush emergence; copper-based biocontrol agents; maintain orchard sanitation by removing infected material',
    chem: 'Azoxystrobin 23 SC @ 1 mL/L or Mancozeb 75 WP @ 2.5 g/L alternating FRAC groups — verify CIB&RC registration before application. PHI: 7 days',
    desc: 'Fungus causes tip dieback of shoots, circular brown spots on fruit surface, post-harvest rotting; most severe in humid conditions; FRAC rotation essential to prevent resistance',
    fallbackSymptoms: [
      'Brown to black sunken circular lesions on fruit surface',
      'Tip dieback of new shoots progressing downward',
      'Salmon-pink spore masses on lesions in humid conditions',
      'Defoliation in severe infections during monsoon',
      'Post-harvest fruit rotting in storage or transit'
    ]
  },
  {
    id: 'fcan',
    category: 'disease',
    name: 'Fruit Canker (Pestalotiopsis psidii)',
    etl: '> 3% fruit with canker lesions at any stage',
    bio: 'Trichoderma viride soil drench; copper-based protectant sprays at fruit set',
    chem: 'Copper oxychloride 50 WP @ 3 g/L or Propiconazole 25 EC @ 1 mL/L — verify CIB&RC registration before application. PHI: 14 days',
    desc: 'Causes raised corky lesions on fruit surface; affects marketability; entry through wounds or insect damage; most prevalent during wet seasons; bagging provides excellent protection',
    fallbackSymptoms: [
      'Small water-soaked spots enlarging to brown corky lesions on fruit',
      'Raised cracked lesion surface with irregular margins',
      'Black acervuli (fruiting bodies) visible in lesion centre',
      'Lesion confined to fruit surface — flesh below may be unaffected initially',
      'Increased incidence near wounds from insect feeding or mechanical damage'
    ]
  },
  {
    id: 'ser',
    category: 'disease',
    name: 'Stylar End Rot (Phytophthora nicotianae / calcium deficiency complex)',
    etl: '> 2% fruit showing stylar end symptoms warrants investigation',
    bio: 'Calcium foliar spray to strengthen cell walls; improve drainage to reduce Phytophthora pressure; Trichoderma drench',
    chem: 'Metalaxyl-M + Mancozeb @ 2.5 g/L if Phytophthora confirmed; CaCl₂ 0.5% foliar if Ca deficiency cause — verify CIB&RC registration before application. PHI: 14 days',
    desc: 'Brown to black rot starting at stylar (blossom) end of fruit; dual cause — either Ca deficiency in rapidly growing fruit or Phytophthora infection in waterlogged conditions; distinguish by soil drainage assessment',
    fallbackSymptoms: [
      'Brown discolouration beginning at the stylar (blossom) end of fruit',
      'Firm dry rot (Ca deficiency type) or soft wet rot (Phytophthora type)',
      'Affected tissue progresses inward from blossom end',
      'Increased incidence after periods of irregular irrigation',
      'Root collar discolouration if Phytophthora root rot also present'
    ]
  }
];

export const FRAC_IRAC_ROTATION = [
  {
    window: 'Spray Window 1 (Bloom / Fruit Set)',
    fungicide: 'Copper oxychloride 50 WP @ 3 g/L (contact protectant)',
    fracGroup: 'FRAC M1 (multi-site — low resistance risk)',
    insecticide: 'Spinosad 45 SC @ 0.5 mL/L bait (avoid bloom timing to protect pollinators)',
    iracGroup: 'IRAC 5 (nicotinic acetylcholine receptor allosteric modulators)'
  },
  {
    window: 'Spray Window 2 (Fruit Development — 30–60 days)',
    fungicide: 'Azoxystrobin 23 SC @ 1 mL/L (systemic, curative)',
    fracGroup: 'FRAC 11 (Qo inhibitor — alternate to avoid resistance)',
    insecticide: 'Chlorantraniliprole 18.5 SC @ 0.4 mL/L',
    iracGroup: 'IRAC 28 (ryanodine receptor modulators)'
  },
  {
    window: 'Spray Window 3 (Pre-Bagging)',
    fungicide: 'Propiconazole 25 EC @ 1 mL/L (DMI fungicide)',
    fracGroup: 'FRAC 3 (demethylation inhibitor — rotate away from FRAC 11)',
    insecticide: 'Neem oil 3 mL/L (OMRI-listed, low resistance risk)',
    iracGroup: 'IRAC UN (multi-mode — resistance break)'
  },
  {
    window: 'Spray Window 4 (Post-Harvest / Next Cycle)',
    fungicide: 'Mancozeb 75 WP @ 2.5 g/L (contact protectant)',
    fracGroup: 'FRAC M3 (multi-site — reset before systemic use)',
    insecticide: 'Imidacloprid 17.8 SL @ 0.5 mL/L stem drench for mealybug',
    iracGroup: 'IRAC 4A (neonicotinoid — use once per cycle only to limit resistance)'
  }
];

// ─────────────────────────────────────────────────────────────────────────────
// TASK 10 — MARKET DATA
// ─────────────────────────────────────────────────────────────────────────────

export const MONTHLY_PRICE_DATA = [
  { month: 'Jan', modal: 20, min: 12, max: 35,  arrivals: 'Very High (>180 t/day)',           score: 2 },
  { month: 'Feb', modal: 32, min: 20, max: 45,  arrivals: 'Moderate (80–120 t/day)',          score: 6 },
  { month: 'Mar', modal: 48, min: 35, max: 65,  arrivals: 'Low (40–70 t/day)',                score: 8 },
  { month: 'Apr', modal: 58, min: 45, max: 75,  arrivals: 'Low (<40 t/day)',                  score: 9 },
  { month: 'May', modal: 52, min: 40, max: 70,  arrivals: 'Very Low (<30 t/day)',             score: 7 },
  { month: 'Jun', modal: 50, min: 30, max: 60,  arrivals: 'Very Low (<35 t/day)',             score: 6 },
  { month: 'Jul', modal: 30, min: 20, max: 45,  arrivals: 'Moderate (60–90 t/day)',           score: 4 },
  { month: 'Aug', modal: 45, min: 30, max: 80,  arrivals: 'Moderate (70–110 t/day)',          score: 7 },
  { month: 'Sep', modal: 55, min: 35, max: 100, arrivals: 'Moderate-Low (60–90 t/day)',       score: 9 },
  { month: 'Oct', modal: 42, min: 30, max: 65,  arrivals: 'Moderate-High (90–130 t/day)',     score: 7 },
  { month: 'Nov', modal: 28, min: 18, max: 45,  arrivals: 'High (120–160 t/day)',             score: 5 },
  { month: 'Dec', modal: 18, min: 10, max: 30,  arrivals: 'Extreme Peak (>200 t/day)',        score: 2 }
];

export const GRADE_ECONOMICS = [
  { grade: 'A+', label: 'Super Jumbo', weightG: '350–500', pack: 'CFB Carton + Foam Net',     priceMin: 70, priceMax: 100 },
  { grade: 'A',  label: 'Premium',     weightG: '250–349', pack: 'CFB Carton + Foam Net',     priceMin: 50, priceMax: 70  },
  { grade: 'B',  label: 'Economy',     weightG: '180–249', pack: 'Plastic Crate / Netted',    priceMin: 30, priceMax: 45  },
  { grade: 'C',  label: 'Cull',        weightG: '<180',    pack: 'Loose Crates / Sacks',      priceMin: 12, priceMax: 22  }
];

export const BAHAR_COMPARISON = [
  { name: 'Mrig Bahar',  flowering: 'Jun–Jul', harvest: 'Nov–Jan', priceRange: '₹12–₹20/kg', modal: 18, verdict: '⚠ AVOID — Peak winter supply glut',         score: 2 },
  { name: 'Ambe Bahar',  flowering: 'Feb–Mar', harvest: 'Aug–Sep', priceRange: '₹45–₹55/kg', modal: 50, verdict: '✓ VIABLE — Protective bagging essential',    score: 7 },
  { name: 'Hasta Bahar', flowering: 'Oct–Nov', harvest: 'Feb–Apr', priceRange: '₹48–₹58/kg', modal: 53, verdict: '✅ OPTIMAL — Spring supply deficit window',   score: 9 }
];

export const NET_REALIZATION_MODEL = [
  { protocol: 'Grade A — CFB Carton, Bagged (750km)',          grossMandi: 65, totalDeductions: 23.58, netFarmGate: 41.42 },
  { protocol: 'Grade B — Plastic Crate, Unbagged (750km)',     grossMandi: 38, totalDeductions: 14.31, netFarmGate: 23.69 }
];

export const PROCUREMENT_BASE = {
  fertilizers: [
    { name: 'Urea (46% N)',                               unit: 'kg', qty2100: 910,    packSize: 50,   packUnit: 'kg bag'       },
    { name: 'MAP 12-61-00 (Mono Ammonium Phosphate)',     unit: 'kg', qty2100: 220,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'MOP 00-00-60 (Muriate of Potash)',           unit: 'kg', qty2100: 455,    packSize: 50,   packUnit: 'kg bag'       },
    { name: 'Calcium Nitrate (15.5% N + 19% Ca)',         unit: 'kg', qty2100: 630,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'Magnesium Sulphate (9.6% Mg)',               unit: 'kg', qty2100: 210,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'MKP 00-52-34 (Mono Potassium Phosphate)',    unit: 'kg', qty2100: 105,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'SOP 00-00-50 (Sulphate of Potash)',          unit: 'kg', qty2100: 546,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'Zinc Sulphate Monohydrate (33% Zn)',         unit: 'kg', qty2100: 53,     packSize: 25,   packUnit: 'kg bag'       },
    { name: 'Borax (11% B)',                              unit: 'kg', qty2100: 21,     packSize: 10,   packUnit: 'kg bag'       },
    { name: 'Fe-EDDHA Chelate (6% Fe)',                   unit: 'kg', qty2100: 21,     packSize: 1,    packUnit: 'kg pack'      }
  ],
  bio: [
    { name: 'Rhizobium biofertilizer',                    unit: 'kg', qty2100: 21,     packSize: 1,    packUnit: 'kg pack'      },
    { name: 'PSB (Phosphate Solubilising Bacteria)',       unit: 'kg', qty2100: 21,     packSize: 1,    packUnit: 'kg pack'      },
    { name: 'Trichoderma viride (1×10⁸ cfu/g)',           unit: 'kg', qty2100: 42,     packSize: 1,    packUnit: 'kg pack'      },
    { name: 'Beauveria bassiana (1×10⁸ cfu/mL)',          unit: 'L',  qty2100: 21,     packSize: 1,    packUnit: 'L bottle'     },
    { name: 'Pseudomonas fluorescens (1×10⁸ cfu/mL)',     unit: 'L',  qty2100: 21,     packSize: 1,    packUnit: 'L bottle'     },
    { name: 'Humic acid granules (70% HA)',                unit: 'kg', qty2100: 210,    packSize: 25,   packUnit: 'kg bag'       },
    { name: 'Neem cake (cold-pressed)',                    unit: 'kg', qty2100: 420,    packSize: 50,   packUnit: 'kg bag'       }
  ],
  hardware: [
    { name: 'Drip tape 16mm (wall 0.2mm)',                 unit: 'm',   qty2100: 6300,  packSize: 1000, packUnit: 'm roll'       },
    { name: 'PC Drippers 4 L/h (pressure compensating)',   unit: 'nos', qty2100: 4200,  packSize: 100,  packUnit: 'piece pack'   },
    { name: 'CFB Cartons (4 kg capacity, double-wall)',     unit: 'nos', qty2100: 26250, packSize: 100,  packUnit: 'piece bundle' },
    { name: 'EPE Foam Nets (guava size)',                   unit: 'nos', qty2100: 105000,packSize: 1000, packUnit: 'piece pack'   },
    { name: 'LDPE Perforated Fruit Bags 8×10 inch',        unit: 'nos', qty2100: 105000,packSize: 1000, packUnit: 'piece pack'   },
    { name: 'Bagging twine / staples',                     unit: 'kg',  qty2100: 11,    packSize: 1,    packUnit: 'kg roll'      },
    { name: 'Methyl eugenol fruit fly traps',              unit: 'nos', qty2100: 210,   packSize: 1,    packUnit: 'piece'        }
  ]
};

export const DIAGNOSTIC_PARAMS = {
  ph: {
    label: 'Soil pH (1:2.5 water)',
    targetRange: '6.5 – 7.5',
    protocol: 'If pH > 7.8: apply Gypsum 500 kg/acre + elemental Sulphur 25 kg/acre to acidify slowly. If pH < 6.5: apply agricultural lime (CaCO₃) 200 kg/acre. Retest after 6 months.'
  },
  ece: {
    label: 'Soil Electrical Conductivity (ECe, dS/m)',
    targetRange: '< 2.0 dS/m',
    protocol: 'If ECe 2–4: deep irrigation leaching (2× normal volume) once per month to flush salts. If ECe > 4: add gypsum + high-volume leaching; consider raised beds. Monitor monthly during summer.'
  },
  oc: {
    label: 'Organic Carbon (%)',
    targetRange: '> 0.8%',
    protocol: 'If OC < 0.5%: apply FYM/vermicompost 10 kg/tree + neem cake 2 kg/tree annually. Green manuring with Dhaincha (Sesbania) in inter-rows. Target > 1% OC over 3 years. Retest annually.'
  },
  avp: {
    label: 'Available Phosphorus (Olsen P, kg/ha)',
    targetRange: '15 – 30 kg/ha',
    protocol: 'If Olsen P < 10: band-apply DAP 50 kg/acre in planting holes + MKP fertigations. If > 40: reduce P inputs; excess P causes Zn/Fe lockout. Retest every 2 years.'
  },
  caco3: {
    label: 'Free CaCO₃ (%)',
    targetRange: '< 10%',
    protocol: 'If CaCO₃ > 15%: switch to chelated micronutrients (EDDHA-Fe, EDTA-Zn); acidify fertigation water with citric acid to pH 6.5; apply elemental S at 25 kg/acre per season. Lime-induced chlorosis management is ongoing.'
  },
  rsc: {
    label: 'Irrigation Water RSC (Residual Sodium Carbonate, meq/L)',
    targetRange: '< 1.25 meq/L',
    protocol: 'If RSC 1.25–2.5: apply Gypsum at a rate calculated from water analysis (meq neutralisation required); acidify with H₂SO₄ or phosphoric acid per water chemistry report. If RSC > 2.5: seek alternative water source or blend with good-quality water.',
    caveat: '⚠ Gypsum and acid dose MUST be calculated from actual water chemistry analysis — do not apply at a fixed rate without a water test.'
  },
  sar: {
    label: 'Irrigation Water SAR (Sodium Adsorption Ratio)',
    targetRange: '< 10',
    protocol: 'If SAR 10–18: apply Gypsum to soil calculated from exchangeable sodium percentage (ESP) and CEC analysis; improve drainage. If SAR > 18: blend with low-SAR water; install subsurface drainage. Deep tillage to break sodium-cemented pans.',
    caveat: '⚠ SAR remediation Gypsum dose MUST be calculated from actual water chemistry and soil CEC analysis — do not apply at a fixed rate without laboratory data.'
  }
};


// ─────────────────────────────────────────────────────────────────────────────
// TASKS 11 & 12 — TRANSLATIONS (English + Hindi)
// Key count in 'hi' MUST equal key count in 'en'
// ─────────────────────────────────────────────────────────────────────────────

export const TRANSLATIONS = {
  en: {
    // Navigation
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

    // Executive KPI labels
    'exec.kpi.trees': 'Total Trees',
    'exec.kpi.months': 'Months to First Harvest',
    'exec.kpi.soil': 'Soil Type',
    'exec.kpi.bahar': 'Bahar Strategy',
    'exec.kpi.price': 'Target Price Range 🔴',
    'exec.kpi.revenue': 'Projected Revenue/Yr 🔴',

    // Executive financial highlights
    'exec.financial.yr2revenue': 'Year-2 First Revenue 🔴',
    'exec.financial.matureRevenue': 'Mature Gross Revenue 🔴',
    'exec.financial.payback': 'Payback Period 🔴',
    'exec.financial.premium': 'Bagging Premium 🔴',

    // Phenological phases
    'exec.phase.1': 'Phase 1: Establishment (Months 8–12)',
    'exec.phase.2': 'Phase 2: Bloom & Fruit Set (Months 13–15)',
    'exec.phase.3': 'Phase 3: Drought & Harvest (Months 16–17)',
    'exec.phase.4': 'Phase 4: Recovery & Cycle 2 (Months 18–24)',

    // Immediate directives
    'exec.directive.1': 'Deblossoming — Remove all flowers',
    'exec.directive.2': 'Canopy Training — Single stem to 60cm',
    'exec.directive.3': 'Drainage Furrows — Excavate between rows',
    'exec.directive.4': 'Biological Inoculation — Trichoderma + PSB root drench',

    // Market tab
    'market.heading': 'Market & Financial Analytics',
    'market.chart.seasonal': 'Seasonal Price Trends — Azadpur Mandi (₹/kg)',
    'market.chart.cashflow': '4-Year Cashflow Projection 🔴 Scenario',
    'market.chart.grade': 'Illustrative Revenue Share by Grade 🔴',
    'market.chart.score': 'Monthly Market Attractiveness Score (1–10)',
    'market.table.yield': 'Yield (kg/tree)',
    'market.table.price': 'Price (₹/kg)',
    'market.table.grossRevenue': 'Gross Revenue (₹) — Scenario Only 🔴',
    'market.table.grade': 'Grade',
    'market.table.weight': 'Weight (g)',
    'market.table.pack': 'Pack Type',
    'market.table.priceRange': 'Price Range (₹/kg)',
    'market.bahar.heading': 'Bahar Comparison',
    'market.bahar.flowering': 'Flowering',
    'market.bahar.harvest': 'Harvest Window',
    'market.bahar.modal': 'Modal Price',
    'market.bahar.verdict': 'Verdict',
    'market.net.heading': 'Net Farm-Gate Realization Model',
    'market.net.protocol': 'Packing Protocol',
    'market.net.gross': 'Gross Mandi (₹/kg)',
    'market.net.deductions': 'Total Deductions (₹/kg)',
    'market.net.net': 'Net Farm-Gate (₹/kg)',

    // Financial simulator
    'simulator.price': 'Average Price (₹/kg)',
    'simulator.yield2': 'Year-2 Yield (kg/tree)',
    'simulator.yield4': 'Mature Yield Year 4+ (kg/tree)',
    'simulator.bagcost': 'Bagging & Packing Cost (₹/fruit)',
    'simulator.gross2': 'Year-2 Gross Revenue',
    'simulator.net2': 'Year-2 Net Income',
    'simulator.gross4': 'Year-4+ Gross Revenue',
    'simulator.net4': 'Year-4+ Net Income',
    'simulator.disclaimer': '🔴 Scenario only — verify with actual buyer prices before harvest',

    // Nutrient Master
    'nutrient.heading': 'Nutrient Master',
    'nutrient.filter.all': 'All Nutrients',
    'nutrient.filter.macro': 'Primary (N/P/K)',
    'nutrient.filter.secondary': 'Secondary (Ca/Mg/S)',
    'nutrient.filter.micro': 'Micronutrients',
    'nutrient.filter.bio': 'Biostimulants',
    'nutrient.role': 'Role',
    'nutrient.impact': 'Crop Impact',
    'nutrient.deficiency': 'Deficiency Symptoms',
    'nutrient.excess': 'Excess / Toxicity',
    'nutrient.doseDrip': 'Drip Dose',
    'nutrient.doseFoliar': 'Foliar Dose',
    'nutrient.doseSoil': 'Soil Application',
    'nutrient.vertisol': 'Vertisol Note',
    'nutrient.antagonism': 'Antagonism',
    'nutrient.evidence': 'Evidence Grade',

    // Farm Calendar
    'calendar.heading': 'Farm Calendar',
    'calendar.instructions': 'Select a month to view detailed agronomic actions',
    'calendar.pheno': 'Phenological Stage',
    'calendar.water': 'Daily Water Requirement',
    'calendar.fert': 'Fertilizer / Fertigation',
    'calendar.foliar': 'Foliar Spray',
    'calendar.pruning': 'Pruning & Training',
    'calendar.ipm': 'IPM Actions',
    'calendar.droughtWarning': '⚠ DROUGHT STOP MONTH — Shut off drip completely',

    // Drip Irrigation Calculator
    'drip.heading': 'Drip Irrigation Calculator',
    'drip.stage': 'Growth Stage',
    'drip.hardware': 'Dripper Configuration',
    'drip.efficiency': 'System Efficiency (η)',
    'drip.vol': 'Volume per Plant (L/day)',
    'drip.runtime': 'Daily Run Time (hours)',
    'drip.orchardTotal': 'Orchard Total (L/day)',
    'drip.formula': 'Formula: V = ET₀ × Kc × Kr × S ÷ η  (S = 6.0 m²)',
    'drip.maintenance': 'Vertisol Drip Maintenance Protocol',

    // Fertigation Schedules
    'fert.heading': 'Fertigation Schedules',
    'fert.rdfHeading': 'Annual RDF Targets (N-P₂O₅-K₂O per tree)',
    'fert.tankHeading': '3-Tank Compatibility Protocol',
    'fert.scheduleHeading': 'Stage 1 WSF Schedule (Months 8–12, 16-week programme)',
    'fert.year': 'Year',
    'fert.npk': 'N-P₂O₅-K₂O (g/tree)',
    'fert.perPlant': 'Per plant/week (g)',
    'fert.per100': 'Per 100 trees/week (g)',
    'fert.orchard': 'Orchard 2100 trees/week (kg)',
    'fert.total16wk': '16-week total (kg)',

    // Crop Health & IPM
    'ipm.heading': 'Crop Health & IPM',
    'ipm.disclaimer': '⚠ All chemical recommendations must be verified against current CIB&RC registration before application.',
    'ipm.searchPlaceholder': 'Search pest or disease...',
    'ipm.filterAll': 'All',
    'ipm.filterInsect': 'Insect Pests',
    'ipm.filterDisease': 'Diseases',
    'ipm.etl': 'Economic Threshold Level',
    'ipm.bio': 'Biological Control',
    'ipm.chem': 'Chemical Control',
    'ipm.symptoms': 'Identification Symptoms',
    'ipm.fracHeading': 'FRAC/IRAC Resistance Rotation Calendar',

    // Fruit Bagging & Diagnostics
    'bagging.heading': 'Fruit Bagging & Diagnostics',
    'bagging.layers': '3-Layer Bagging System',
    'bagging.preSpray': 'Pre-Bagging Spray Directive',
    'bagging.diagHeading': 'Soil & Water Diagnostic Lookup',
    'bagging.diagSelect': 'Select parameter to look up',
    'bagging.caveats': 'RSC/SAR Remediation Caveats',

    // Procurement Calculator
    'procurement.heading': 'Procurement Calculator',
    'procurement.treeCount': 'Tree Count',
    'procurement.fertilizers': 'Fertilizers & WSF',
    'procurement.bio': 'Micronutrients & Bio-Agents',
    'procurement.hardware': 'Hardware & Bagging Supplies',
    'procurement.scalingNote': 'Base quantities keyed to 2,100 trees. Scaling: actual trees ÷ 2,100 × base quantity, rounded up to nearest commercial unit.',
    'procurement.priceNote': '🔴 Prices and availability must be verified with local suppliers at time of purchase.',

    // Critical Warnings
    'warnings.heading': 'Critical Warnings',
    'warnings.intro': 'The following practices carry documented risk of significant crop loss or tree mortality. Review before each operational phase.',
    'warnings.card1.title': '⛔ Premature Cropping (Year 1)',
    'warnings.card1.body': 'Allowing fruit to develop in the first year diverts energy from root and canopy establishment. Remove all flowers and fruitlets in Months 8–12. Trees that fruit prematurely show reduced vigour and yield decline in subsequent seasons.',
    'warnings.card2.title': '⛔ Root-Collar Waterlogging on Vertisol',
    'warnings.card2.body': 'Vertisols shrink-swell and can pond water at the root collar. Sustained waterlogging > 48 hours causes root asphyxiation and opens entry points for Fusarium wilt. Excavate drainage furrows before monsoon and maintain them.',
    'warnings.card3.title': '⚠ Tractor Rotovation Near Trunk',
    'warnings.card3.body': 'Rotovating within 1.5m of the trunk severs feeder roots and causes mechanical wounds that are entry points for bark-eating caterpillars and Phytophthora. Use hand-weeding or mulching within the root zone.',
    'warnings.card4.title': '⚠ Glyphosate Drift',
    'warnings.card4.body': 'Glyphosate spray drift on green wood causes defoliation and systemic damage. Sub-lethal doses cause progressive dieback without clear cause. Use shielded applicators only; maintain minimum 3m buffer from canopy edge.',
    'warnings.card5.title': '⛔ Calcium Nitrate + Phosphate/Sulphate Tank Mixing',
    'warnings.card5.body': 'Mixing Calcium Nitrate with phosphate fertilizers (MAP, DAP, MKP) or sulfates (SOP, MgSO₄) in the same tank causes immediate precipitation, blocking drippers and wasting inputs. Always use separate tanks (Tank A for Ca Nitrate, Tank B for phosphates).',
    'warnings.card6.title': '⚠ Unperforated Plastic Bagging',
    'warnings.card6.body': 'Sealed plastic bags trap humidity around fruit, promoting Anthracnose, Stylar End Rot, and physiological disorders. Use only perforated LDPE bags or approved paper bags with adequate ventilation.',
    'warnings.card7.title': '⚠ Insecticide Spray During Full Bloom',
    'warnings.card7.body': 'Broad-spectrum insecticide application during anthesis kills pollinators and reduces fruit set. Suspend chemical insecticide applications during full bloom (typically 7–10 days). Use only sticky traps and pheromone lures during this window.',
    'warnings.card8.title': '⛔ Chemical Deblossoming (Urea/NAA on Trees < 12 Months)',
    'warnings.card8.body': 'Spraying Urea at high concentration or NAA on trees under 12 months causes phytotoxic leaf burn and systemic stress. Manual deblossoming (hand removal of all flower buds) is the recommended and safe alternative for Year-1 trees.',
    'warnings.card9.title': '⚠ Re-irrigation After Prolonged Drought Without Buffering',
    'warnings.card9.body': 'Resuming full irrigation volume immediately after the Month-16 drought stress period causes fruit splitting and osmotic shock. Reintroduce irrigation gradually over 5–7 days at 30% → 60% → 100% of normal volume.',

    // Common keys
    'common.scenario': '🔴 Scenario only',
    'common.source': 'Source',
    'common.evidenceLegend.A': '🟢 A — NHB/ICAR Official Recommendation',
    'common.evidenceLegend.B': '🔵 B — Peer-reviewed research on Psidium guajava',
    'common.evidenceLegend.C': '🟡 C — Local adaptation; calibration required before use',
    'common.evidenceLegend.E': '🔴 E — Scenario / Forecast only; not a guarantee',
    'common.disclaimer.financial': 'All financial projections are planning scenarios only (🔴 Scenario). Verify all prices with buyers before harvest. NHB/ICAR agronomic references used where stated.',
    'common.disclaimer.pesticide': '⚠ All pesticide recommendations must be verified against current CIB&RC registration. Pre-harvest intervals (PHI) must be observed. Kiro and this dashboard do not accept liability for crop or regulatory outcomes.'
  },

  hi: {
    // Navigation
    'nav.tab1': 'डैशबोर्ड अवलोकन',
    'nav.tab2': 'बाजार और वित्तीय विश्लेषण',
    'nav.tab3': 'पोषक तत्व मास्टर',
    'nav.tab4': 'कृषि कैलेंडर',
    'nav.tab5': 'ड्रिप सिंचाई कैलकुलेटर',
    'nav.tab6': 'फर्टिगेशन शेड्यूल',
    'nav.tab7': 'फसल स्वास्थ्य और IPM',
    'nav.tab8': 'फल बैगिंग और डायग्नोस्टिक्स',
    'nav.tab9': 'खरीद कैलकुलेटर',
    'nav.tab10': 'महत्वपूर्ण चेतावनियाँ',

    // Executive KPI labels
    'exec.kpi.trees': 'कुल पेड़',
    'exec.kpi.months': 'पहली फसल तक महीने',
    'exec.kpi.soil': 'मिट्टी का प्रकार',
    'exec.kpi.bahar': 'बहार रणनीति',
    'exec.kpi.price': 'लक्ष्य मूल्य सीमा 🔴',
    'exec.kpi.revenue': 'अनुमानित आय/वर्ष 🔴',

    // Executive financial highlights
    'exec.financial.yr2revenue': 'वर्ष-2 प्रथम राजस्व 🔴',
    'exec.financial.matureRevenue': 'परिपक्व सकल राजस्व 🔴',
    'exec.financial.payback': 'पूंजी वापसी अवधि 🔴',
    'exec.financial.premium': 'बैगिंग प्रीमियम 🔴',

    // Phenological phases
    'exec.phase.1': 'चरण 1: स्थापना (माह 8–12)',
    'exec.phase.2': 'चरण 2: फूल और फल सेट (माह 13–15)',
    'exec.phase.3': 'चरण 3: सूखा तनाव और फसल (माह 16–17)',
    'exec.phase.4': 'चरण 4: पुनर्प्राप्ति और चक्र 2 (माह 18–24)',

    // Immediate directives
    'exec.directive.1': 'डिब्लॉसमिंग — सभी फूल हटाएं',
    'exec.directive.2': 'कैनोपी प्रशिक्षण — एकल तना 60 सेमी तक',
    'exec.directive.3': 'जल निकासी खाई — पंक्तियों के बीच खोदें',
    'exec.directive.4': 'जैविक टीकाकरण — ट्राइकोडर्मा + PSB जड़ ड्रेंच',

    // Market tab
    'market.heading': 'बाजार और वित्तीय विश्लेषण',
    'market.chart.seasonal': 'मौसमी मूल्य प्रवृत्ति — आजादपुर मंडी (₹/किग्रा)',
    'market.chart.cashflow': '4-वर्ष नकदी प्रवाह प्रक्षेपण 🔴 परिदृश्य',
    'market.chart.grade': 'ग्रेड अनुसार राजस्व हिस्सेदारी 🔴 (सांकेतिक)',
    'market.chart.score': 'मासिक बाजार आकर्षकता स्कोर (1–10)',
    'market.table.yield': 'उपज (किग्रा/पेड़)',
    'market.table.price': 'मूल्य (₹/किग्रा)',
    'market.table.grossRevenue': 'सकल राजस्व (₹) — केवल परिदृश्य 🔴',
    'market.table.grade': 'ग्रेड',
    'market.table.weight': 'वजन (ग्रा)',
    'market.table.pack': 'पैकिंग प्रकार',
    'market.table.priceRange': 'मूल्य सीमा (₹/किग्रा)',
    'market.bahar.heading': 'बहार तुलना',
    'market.bahar.flowering': 'फूल आने का समय',
    'market.bahar.harvest': 'फसल खिड़की',
    'market.bahar.modal': 'मोडल मूल्य',
    'market.bahar.verdict': 'निर्णय',
    'market.net.heading': 'शुद्ध खेत-गेट प्राप्ति मॉडल',
    'market.net.protocol': 'पैकिंग प्रोटोकॉल',
    'market.net.gross': 'सकल मंडी (₹/किग्रा)',
    'market.net.deductions': 'कुल कटौती (₹/किग्रा)',
    'market.net.net': 'शुद्ध खेत-गेट (₹/किग्रा)',

    // Financial simulator
    'simulator.price': 'औसत मूल्य (₹/किग्रा)',
    'simulator.yield2': 'वर्ष-2 उपज (किग्रा/पेड़)',
    'simulator.yield4': 'परिपक्व उपज वर्ष 4+ (किग्रा/पेड़)',
    'simulator.bagcost': 'बैगिंग और पैकिंग लागत (₹/फल)',
    'simulator.gross2': 'वर्ष-2 सकल राजस्व',
    'simulator.net2': 'वर्ष-2 शुद्ध आय',
    'simulator.gross4': 'वर्ष-4+ सकल राजस्व',
    'simulator.net4': 'वर्ष-4+ शुद्ध आय',
    'simulator.disclaimer': '🔴 केवल परिदृश्य — फसल से पहले वास्तविक खरीदार मूल्यों से सत्यापित करें',

    // Nutrient Master
    'nutrient.heading': 'पोषक तत्व मास्टर',
    'nutrient.filter.all': 'सभी पोषक तत्व',
    'nutrient.filter.macro': 'प्राथमिक (N/P/K)',
    'nutrient.filter.secondary': 'द्वितीयक (Ca/Mg/S)',
    'nutrient.filter.micro': 'सूक्ष्म पोषक तत्व',
    'nutrient.filter.bio': 'जैव उत्तेजक',
    'nutrient.role': 'भूमिका',
    'nutrient.impact': 'फसल प्रभाव',
    'nutrient.deficiency': 'कमी के लक्षण',
    'nutrient.excess': 'अधिकता / विषाक्तता',
    'nutrient.doseDrip': 'ड्रिप खुराक',
    'nutrient.doseFoliar': 'पर्णीय खुराक',
    'nutrient.doseSoil': 'मिट्टी प्रयोग',
    'nutrient.vertisol': 'वर्टिसोल नोट',
    'nutrient.antagonism': 'विरोधाभास',
    'nutrient.evidence': 'साक्ष्य ग्रेड',

    // Farm Calendar
    'calendar.heading': 'कृषि कैलेंडर',
    'calendar.instructions': 'विस्तृत कृषि कार्यों के लिए महीना चुनें',
    'calendar.pheno': 'फेनोलॉजिकल अवस्था',
    'calendar.water': 'दैनिक जल आवश्यकता',
    'calendar.fert': 'उर्वरक / फर्टिगेशन',
    'calendar.foliar': 'पर्णीय छिड़काव',
    'calendar.pruning': 'छंटाई और प्रशिक्षण',
    'calendar.ipm': 'IPM कार्य',
    'calendar.droughtWarning': '⚠ सूखा रोक माह — ड्रिप पूरी तरह बंद करें',

    // Drip Irrigation Calculator
    'drip.heading': 'ड्रिप सिंचाई कैलकुलेटर',
    'drip.stage': 'वृद्धि अवस्था',
    'drip.hardware': 'ड्रिपर कॉन्फ़िगरेशन',
    'drip.efficiency': 'सिस्टम दक्षता (η)',
    'drip.vol': 'प्रति पेड़ मात्रा (लीटर/दिन)',
    'drip.runtime': 'दैनिक चलने का समय (घंटे)',
    'drip.orchardTotal': 'बाग कुल (लीटर/दिन)',
    'drip.formula': 'सूत्र: V = ET₀ × Kc × Kr × S ÷ η  (S = 6.0 m²)',
    'drip.maintenance': 'वर्टिसोल ड्रिप रखरखाव प्रोटोकॉल',

    // Fertigation Schedules
    'fert.heading': 'फर्टिगेशन शेड्यूल',
    'fert.rdfHeading': 'वार्षिक RDF लक्ष्य (N-P₂O₅-K₂O प्रति पेड़)',
    'fert.tankHeading': '3-टैंक संगतता प्रोटोकॉल',
    'fert.scheduleHeading': 'स्टेज 1 WSF शेड्यूल (माह 8–12, 16-सप्ताह कार्यक्रम)',
    'fert.year': 'वर्ष',
    'fert.npk': 'N-P₂O₅-K₂O (ग्रा/पेड़)',
    'fert.perPlant': 'प्रति पेड़/सप्ताह (ग्रा)',
    'fert.per100': 'प्रति 100 पेड़/सप्ताह (ग्रा)',
    'fert.orchard': 'बाग 2100 पेड़/सप्ताह (किग्रा)',
    'fert.total16wk': '16-सप्ताह कुल (किग्रा)',

    // Crop Health & IPM
    'ipm.heading': 'फसल स्वास्थ्य और IPM',
    'ipm.disclaimer': '⚠ सभी रासायनिक सिफारिशों को आवेदन से पहले वर्तमान CIB&RC पंजीकरण के विरुद्ध सत्यापित किया जाना चाहिए।',
    'ipm.searchPlaceholder': 'कीट या रोग खोजें...',
    'ipm.filterAll': 'सभी',
    'ipm.filterInsect': 'कीट',
    'ipm.filterDisease': 'रोग',
    'ipm.etl': 'आर्थिक दहलीज स्तर',
    'ipm.bio': 'जैविक नियंत्रण',
    'ipm.chem': 'रासायनिक नियंत्रण',
    'ipm.symptoms': 'पहचान के लक्षण',
    'ipm.fracHeading': 'FRAC/IRAC प्रतिरोध रोटेशन कैलेंडर',

    // Fruit Bagging & Diagnostics
    'bagging.heading': 'फल बैगिंग और डायग्नोस्टिक्स',
    'bagging.layers': '3-परत बैगिंग प्रणाली',
    'bagging.preSpray': 'बैगिंग पूर्व छिड़काव निर्देश',
    'bagging.diagHeading': 'मिट्टी और जल निदान लुकअप',
    'bagging.diagSelect': 'पैरामीटर चुनें',
    'bagging.caveats': 'RSC/SAR उपचार सावधानियाँ',

    // Procurement Calculator
    'procurement.heading': 'खरीद कैलकुलेटर',
    'procurement.treeCount': 'पेड़ों की संख्या',
    'procurement.fertilizers': 'उर्वरक और WSF',
    'procurement.bio': 'सूक्ष्म पोषक और जैव एजेंट',
    'procurement.hardware': 'हार्डवेयर और बैगिंग सामग्री',
    'procurement.scalingNote': 'आधार मात्रा 2,100 पेड़ों के लिए। स्केलिंग: वास्तविक पेड़ ÷ 2,100 × आधार मात्रा, निकटतम व्यावसायिक इकाई तक गोल।',
    'procurement.priceNote': '🔴 कीमतें और उपलब्धता खरीद के समय स्थानीय आपूर्तिकर्ताओं से सत्यापित करें।',

    // Critical Warnings
    'warnings.heading': 'महत्वपूर्ण चेतावनियाँ',
    'warnings.intro': 'निम्नलिखित प्रथाओं से महत्वपूर्ण फसल हानि या पेड़ मृत्यु का प्रलेखित जोखिम है। प्रत्येक परिचालन चरण से पहले समीक्षा करें।',
    'warnings.card1.title': '⛔ समय से पहले फसल (वर्ष 1)',
    'warnings.card1.body': 'पहले वर्ष में फल विकास की अनुमति देने से जड़ और छत्र स्थापना से ऊर्जा मुड़ जाती है। माह 8–12 में सभी फूल और फलेट हटाएं।',
    'warnings.card2.title': '⛔ वर्टिसोल पर जड़ कॉलर जलभराव',
    'warnings.card2.body': 'वर्टिसोल सिकुड़-फूलते हैं और जड़ कॉलर पर पानी जमा हो सकता है। 48 घंटे से अधिक जलभराव जड़ श्वासावरोध करता है।',
    'warnings.card3.title': '⚠ ट्रंक के पास ट्रैक्टर रोटोवेशन',
    'warnings.card3.body': 'ट्रंक के 1.5 मीटर के भीतर रोटोवेटिंग से फीडर जड़ें कट जाती हैं और यांत्रिक घाव बनते हैं।',
    'warnings.card4.title': '⚠ ग्लाइफोसेट बहाव',
    'warnings.card4.body': 'हरी लकड़ी पर ग्लाइफोसेट छिड़काव बहाव से पर्णपात और प्रणालीगत क्षति होती है।',
    'warnings.card5.title': '⛔ कैल्शियम नाइट्रेट + फॉस्फेट/सल्फेट टैंक मिश्रण',
    'warnings.card5.body': 'एक ही टैंक में कैल्शियम नाइट्रेट को फॉस्फेट (MAP, DAP, MKP) या सल्फेट के साथ मिलाने से तुरंत अवक्षेपण होता है।',
    'warnings.card6.title': '⚠ अछिद्रित प्लास्टिक बैगिंग',
    'warnings.card6.body': 'सील्ड प्लास्टिक बैग फल के चारों ओर नमी फंसाते हैं, एन्थ्रेक्नोज और शारीरिक विकारों को बढ़ावा देते हैं।',
    'warnings.card7.title': '⚠ पूर्ण फूल के दौरान कीटनाशक छिड़काव',
    'warnings.card7.body': 'परागकाल में व्यापक-स्पेक्ट्रम कीटनाशक परागकर्ताओं को मारते हैं और फल सेट कम करते हैं।',
    'warnings.card8.title': '⛔ रासायनिक डिब्लॉसमिंग (12 माह से कम के पेड़ों पर यूरिया/NAA)',
    'warnings.card8.body': 'उच्च सांद्रता में यूरिया या NAA का 12 माह से कम के पेड़ों पर छिड़काव फाइटोटॉक्सिक पत्ती जलन करता है। हाथ से फूल हटाना सुरक्षित विकल्प है।',
    'warnings.card9.title': '⚠ बिना बफरिंग के सूखे के बाद पुनः सिंचाई',
    'warnings.card9.body': 'माह-16 सूखा तनाव अवधि के बाद तुरंत पूर्ण सिंचाई मात्रा शुरू करने से फल फटना होता है। 5–7 दिनों में धीरे-धीरे पुनः आरंभ करें।',

    // Common keys
    'common.scenario': '🔴 केवल परिदृश्य',
    'common.source': 'स्रोत',
    'common.evidenceLegend.A': '🟢 A — NHB/ICAR आधिकारिक अनुशंसा',
    'common.evidenceLegend.B': '🔵 B — Psidium guajava पर सहकर्मी-समीक्षित अनुसंधान',
    'common.evidenceLegend.C': '🟡 C — स्थानीय अनुकूलन; उपयोग से पहले अंशांकन आवश्यक',
    'common.evidenceLegend.E': '🔴 E — केवल परिदृश्य/पूर्वानुमान; गारंटी नहीं',
    'common.disclaimer.financial': 'सभी वित्तीय अनुमान केवल योजना परिदृश्य हैं (🔴 परिदृश्य)। फसल से पहले खरीदारों के साथ सभी कीमतें सत्यापित करें।',
    'common.disclaimer.pesticide': '⚠ सभी कीटनाशक सिफारिशों को वर्तमान CIB&RC पंजीकरण के विरुद्ध सत्यापित किया जाना चाहिए।'
  }
};
