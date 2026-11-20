/**
 * charts-data.js - the only static tables js/charts.js needs.
 * Moved from data.js; all other static agronomy tables there were unused and were removed.
 */
// TASK 6 — ORCHARD CONSTANTS
// CASE STUDY, NOT MARKET DATA: these figures describe the owner's own
// 2100-tree Taiwan Pink orchard. Market prices come from the live mandi API
// (Agmarknet / data.gov.in); no price table is stored in this file.
// ─────────────────────────────────────────────────────────────────────────────

export const ORCHARD = {
  trees: 2100,
  avgFruitWeightKg: 0.400,
  spacingM2: 6.0
};

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
