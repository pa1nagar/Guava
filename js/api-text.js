/**
 * api-text.js — Hindi for the fixed English sentences the backend sends.
 *
 * The API returns some text as English only (basis notes, irrigation and climate messages,
 * disease alerts, fixed plan notes). translateApiText(text, lang) returns the Hindi version when the
 * sentence is in the table below, and the original text otherwise. It never returns blank.
 *
 * Source of the sentences: backend/services/weather.py, climate.py, routers/insights.py,
 * routers/activities.py (gaps), routers/plan.py. Text written by the AI planner (summary, task
 * descriptions) is free text and is not translated here.
 *
 * Safety: the Hindi alerts keep the same meaning as the English ones. They tell the farmer to
 * inspect the orchard and ask the local agriculture officer (KVK). They never name a product or a dose.
 */

const KVK_EN = " Ask your local agriculture officer (KVK) before any spray.";
const KVK_HI = " कोई भी स्प्रे करने से पहले अपने स्थानीय कृषि अधिकारी (KVK) से पूछें।";

const EXACT = {
  // basis notes
  "Rule of thumb on forecast temperature and rain; not from a published source. It is a prompt to inspect the orchard, not a diagnosis.":
    "यह अनुमानित तापमान और बारिश पर आधारित एक मोटा नियम है, किसी प्रकाशित स्रोत से नहीं। यह बाग देखने की याद दिलाता है, बीमारी की पहचान नहीं।",
  "Estimate. Flat crop coefficient 0.85 for all growth stages, and the demand bands (above 6 and above 3 mm/day) are rules of thumb, not from a source. Check the soil before changing your schedule.":
    "अनुमान। सभी चरणों के लिए एक ही फसल गुणांक 0.85 लिया गया है, और पानी की माँग के स्तर (6 और 3 मिमी/दिन से ऊपर) मोटे नियम हैं, किसी स्रोत से नहीं। अपना कार्यक्रम बदलने से पहले मिट्टी जाँच लें।",
  "Estimate typed in by the app developer; no published source. Compare with the calendar stage, do not use alone.":
    "यह ऐप बनाने वाले का दर्ज किया हुआ अनुमान है, कोई प्रकाशित स्रोत नहीं। इसे कैलेंडर वाले चरण से मिलाकर देखें, अकेले इस्तेमाल न करें।",
  "Reference prices typed in by the app developer, undated, not live market rates; check your dealer price.":
    "ये संदर्भ भाव ऐप बनाने वाले ने दर्ज किए हैं, बिना तारीख के और बाज़ार के ताज़ा भाव नहीं हैं। अपने डीलर से भाव पूछ लें।",
  "Estimated date: a calendar assumption of 17 months x 30 days after sowing, not a measurement. Prices shown are saved past prices, not a forecast.":
    "अनुमानित तारीख: रोपण के 17 महीने × 30 दिन का कैलेंडर अनुमान, कोई माप नहीं। दिखाए गए भाव पहले सहेजे गए भाव हैं, पूर्वानुमान नहीं।",
  // irrigation advisory
  "ET0 data unavailable.": "ET0 का डेटा उपलब्ध नहीं है।",
  "Drought stress period — do not irrigate.": "सूखे का दौर है, सिंचाई न करें।",
  // climate and gdd
  "Climate data unavailable for this period.": "इस अवधि के लिए मौसम का डेटा उपलब्ध नहीं है।",
  "Temperature and rainfall are close to the 30-year average this month.":
    "इस महीने तापमान और बारिश 30 साल के औसत के पास हैं।",
  "Rainfall within normal range. No waterlogging risk.": "बारिश सामान्य सीमा में है। जलभराव का जोखिम नहीं है।",
  "Heat accumulation suggests your crop may be developing faster than the calendar month indicates.":
    "ऊष्मा जमा होने से लगता है कि आपकी फसल कैलेंडर के महीने से तेज़ बढ़ रही है।",
  "Cooler-than-normal temperatures may be slowing crop development relative to calendar months.":
    "सामान्य से ठंडा तापमान फसल की बढ़त को कैलेंडर के महीनों के मुकाबले धीमा कर सकता है।",
  "Heat accumulation is consistent with the calendar-based stage.":
    "ऊष्मा का जमाव कैलेंडर वाले चरण से मेल खाता है।",
  // plan notes
  "Plan generated from reference data (AI explanation unavailable).":
    "योजना संदर्भ डेटा से बनी है (AI की व्याख्या उपलब्ध नहीं)।",
  // disease names and levels
  "Anthracnose / Fruit rot": "एंथ्रेक्नोज़ / फल सड़न",
  "Fruit fly": "फल मक्खी",
  "Powdery mildew": "चूर्णिल आसिता (पाउडरी मिल्ड्यू)",
  "Stem / Bark borer": "तना / छाल छेदक",
  "Guava wilt (Fusarium)": "अमरूद का उकठा (फ्यूज़ेरियम)",
  High: "ज़्यादा",
  Moderate: "मध्यम",
  Elevated: "बढ़ा हुआ",
  // stage labels from backend/data/crop_knowledge.json
  Establishment: "स्थापना",
  "Vegetative Growth": "वानस्पतिक बढ़त",
  "Post-Monsoon Establishment": "मानसून के बाद की स्थापना",
  "Pre-Bloom Hardening": "फूल आने से पहले की मज़बूती",
  "Bloom and Fruit Set": "फूल और फल बनना",
  "Fruit Development": "फल का विकास",
  "Drought Stress": "सूखे का दौर",
  Harvest: "कटाई",
  "Post-Harvest and Recovery": "कटाई के बाद और सुधार",
};

// Disease alert advice (the KVK sentence is appended by the backend and handled separately).
const ADVICE = {
  "Warm, wet weather favours fruit rot. Walk the orchard, remove and bury rotting fruit, and keep the canopy open to air.":
    "गर्म और नम मौसम फल सड़न को बढ़ाता है। बाग में घूमकर देखें, सड़े फल हटाकर गाड़ दें और पेड़ की छतरी को हवादार रखें।",
  "Warm, dry weather favours fruit fly. Check your traps daily and collect fallen fruit.":
    "गर्म और सूखा मौसम फल मक्खी को बढ़ाता है। जाल रोज़ देखें और गिरे हुए फल उठा लें।",
  "Monitor young shoots for a white powder on the leaves. Remove badly affected shoots.":
    "नई टहनियों पर पत्तियों में सफ़ेद पाउडर देखते रहें। बहुत प्रभावित टहनियाँ हटा दें।",
  "Inspect shoot tips for wilting or entry holes. Remove affected shoots.":
    "टहनी के सिरों पर मुरझाना या छेद देखें। प्रभावित टहनियाँ हटा दें।",
  "Check the root zone for waterlogging. Keep drainage channels clear.":
    "जड़ वाले हिस्से में पानी रुकने की जाँच करें। नालियाँ साफ़ रखें।",
};

const ACTIVITY_HI = {
  fertilizer: "खाद",
  irrigation: "सिंचाई",
  pesticide: "कीटनाशक",
  labour: "मज़दूरी",
  other: "अन्य",
};

const COMPLIANCE_TAIL = {
  good: "खाद की मात्रा सुझाए गए कार्यक्रम के पास है। उपज की संभावना ठीक बनी हुई है।",
  moderate: "उपज बचाने के लिए अगले चरण में खाद की कमी पूरी करने पर विचार करें।",
};

// [pattern, builder]. Patterns match the whole sentence the backend sends.
const TEMPLATES = [
  [/^ET0 is ([\d.]+) mm\/day — water demand is high\. Do not reduce irrigation today\.$/,
    (m) => `ET0 ${m[1]} मिमी/दिन है। पानी की माँग ज़्यादा है। आज सिंचाई कम न करें।`],
  [/^ET0 is ([\d.]+) mm\/day — normal water demand\. Maintain reference schedule\.$/,
    (m) => `ET0 ${m[1]} मिमी/दिन है। पानी की माँग सामान्य है। संदर्भ कार्यक्रम जारी रखें।`],
  [/^ET0 is ([\d.]+) mm\/day — cool\/cloudy conditions\. You may irrigate a little less if the soil is still moist\.$/,
    (m) => `ET0 ${m[1]} मिमी/दिन है। मौसम ठंडा या बादल वाला है। मिट्टी नम हो तो सिंचाई थोड़ी कम कर सकते हैं।`],
  [/^This month is (.+)\.$/, (m) => {
    const parts = m[1].split(" and ").map((p) => {
      let x = p.match(/^([\d.]+)°C (warmer|cooler) than the 30-year average$/);
      if (x) return `तापमान 30 साल के औसत से ${x[1]}°C ${x[2] === "warmer" ? "ज़्यादा" : "कम"}`;
      x = p.match(/^(\d+)mm (more|less) rainfall than normal$/);
      if (x) return `बारिश सामान्य से ${x[1]} मिमी ${x[2] === "more" ? "ज़्यादा" : "कम"}`;
      return null;
    });
    return parts.every(Boolean) ? `इस महीने ${parts.join(" और ")} है।` : null;
  }],
  [/^Rainfall is (\d+)% above normal\. High risk of waterlogging and Fusarium wilt\. Clear drainage furrows\.$/,
    (m) => `बारिश सामान्य से ${m[1]}% ज़्यादा है। जलभराव और फ्यूज़ेरियम उकठे का जोखिम ज़्यादा है। पानी निकासी की नालियाँ साफ़ करें।`],
  [/^Rainfall is (\d+)% above normal\. Check drainage\.$/,
    (m) => `बारिश सामान्य से ${m[1]}% ज़्यादा है। पानी निकासी जाँच लें।`],
  [/^Rainfall is (\d+)% below normal\. Increase irrigation to compensate\.$/,
    (m) => `बारिश सामान्य से ${m[1]}% कम है। कमी पूरी करने के लिए सिंचाई बढ़ाएँ।`],
  [/^Good compliance \((\d+)\/100\)\. Fertilizer inputs are close to the recommended schedule\. Yield potential is well-maintained\.$/,
    (m) => `अच्छा पालन (${m[1]}/100)। ${COMPLIANCE_TAIL.good}`],
  [/^Moderate compliance \((\d+)\/100\)\. Consider catching up on fertilizer in the next stage to protect yield\.$/,
    (m) => `मध्यम पालन (${m[1]}/100)। ${COMPLIANCE_TAIL.moderate}`],
  [/^Low compliance \((\d+)\/100\)\. Only (\d+)% of expected fertilizer was logged\. Significant yield reduction is likely\.$/,
    (m) => `कम पालन (${m[1]}/100)। अपेक्षित खाद का सिर्फ़ ${m[2]}% दर्ज हुआ है। उपज में काफ़ी कमी हो सकती है।`],
  [/^You may be behind on (\w+) for this stage\.$/, (m) => {
    const a = ACTIVITY_HI[m[1]];
    return a ? `इस चरण में आप ${a} में पीछे हो सकते हैं।` : null;
  }],
  [/^Month (\d+) — (.+)$/, (m, lang) => `महीना ${m[1]} — ${translateApiText(m[2], lang)}`],
];

/**
 * @param {string} text English text from the API
 * @param {'en'|'hi'} lang
 * @returns {string} Hindi when known and lang is "hi", otherwise the original text.
 */
export function translateApiText(text, lang) {
  if (text == null) return "";
  const s = String(text);
  if (lang !== "hi" || !s) return s;
  if (EXACT[s]) return EXACT[s];
  if (s.endsWith(KVK_EN)) {
    const advice = ADVICE[s.slice(0, -KVK_EN.length)];
    if (advice) return advice + KVK_HI;
  }
  if (ADVICE[s]) return ADVICE[s];
  for (const [re, build] of TEMPLATES) {
    const m = s.match(re);
    if (m) {
      const out = build(m, lang);
      if (out) return out;
    }
  }
  return s;
}

/** Hindi name of an activity type such as "Fertilizer" (falls back to the English name). */
export function activityTypeLabel(type, lang) {
  if (lang !== "hi") return String(type ?? "");
  return ACTIVITY_HI[String(type ?? "").toLowerCase()] || String(type ?? "");
}
