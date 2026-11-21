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
  guava: "अमरूद", Guava: "अमरूद",
  "Pre-Bloom": "फूल आने से पहले",
  // financial notes (backend/routers/financial.py)
  "Set an expected yield to calculate your break-even price.":
    "अपना ब्रेक-ईवन भाव निकालने के लिए अपेक्षित उपज दर्ज करें।",
  "Break-even needs an expected yield.": "ब्रेक-ईवन निकालने के लिए अपेक्षित उपज चाहिए।",
  "No costs logged yet.": "अभी तक कोई खर्च दर्ज नहीं हुआ है।",
  "Harvest has already been recorded for this crop cycle.": "इस फसल चक्र की कटाई पहले ही दर्ज हो चुकी है।",
  "Profile not found.": "प्रोफ़ाइल नहीं मिली।",
  "Activity not found.": "गतिविधि नहीं मिली।",
  "Observation not found.": "अवलोकन नहीं मिला।",
  "Photo not found.": "फोटो नहीं मिली।",
  "Crop not supported.": "यह फसल अभी उपलब्ध नहीं है।",
  "Planting date cannot be in the future.": "रोपण की तारीख आगे की नहीं हो सकती।",
  "Cannot determine crop stage.": "फसल का चरण तय नहीं हो सका।",
  "Farm not found.": "खेत नहीं मिला।",
  "Plot not found.": "प्लॉट नहीं मिला।",
  "Database error.": "डेटा सहेजने या पढ़ने में दिक्कत आई। कृपया फिर कोशिश करें।",
  "Could not submit form.": "फ़ॉर्म जमा नहीं हो सका। कृपया फिर कोशिश करें।",
  "status must be one of: planned, recorded": "स्थिति 'योजनाबद्ध' या 'दर्ज' में से एक होनी चाहिए।",
  "Could not process image file. Ensure it is a valid image.": "फोटो खोली नहीं जा सकी। कृपया सही फोटो चुनें।",
  // weather and climate fetch failures
  "Weather data temporarily unavailable.": "मौसम का डेटा अभी उपलब्ध नहीं है।",
  "Climate baseline data unavailable.": "मौसम के औसत का डेटा उपलब्ध नहीं है।",
  // weather descriptions (backend/services/weather.py WMO_DESCRIPTIONS)
  "Clear sky": "साफ़ आसमान", "Mainly clear": "ज़्यादातर साफ़", "Partly cloudy": "आंशिक बादल", Overcast: "घने बादल",
  Fog: "कोहरा", "Depositing rime fog": "पाला जमाने वाला कोहरा",
  "Light drizzle": "हल्की फुहार", "Moderate drizzle": "मध्यम फुहार", "Dense drizzle": "घनी फुहार",
  "Slight rain": "हल्की बारिश", "Moderate rain": "मध्यम बारिश", "Heavy rain": "भारी बारिश",
  "Slight showers": "हल्की बौछारें", "Moderate showers": "मध्यम बौछारें", "Violent showers": "तेज़ बौछारें",
  Thunderstorm: "आँधी-बारिश", "Thunderstorm with hail": "ओलों के साथ आँधी-बारिश",
  // plan tasks and notes (backend/routers/plan.py)
  Irrigation: "सिंचाई",
  "Irrigation — Drought Stress Period": "सिंचाई — सूखे का दौर",
  "Stop all irrigation this week.": "इस हफ़्ते सारी सिंचाई बंद रखें।",
  "litres/day (total for all plants)": "लीटर/दिन (सभी पौधों के लिए कुल)",
  "kg/week (total for all plants)": "किग्रा/हफ़्ता (सभी पौधों के लिए कुल)",
  "litres/day": "लीटर/दिन",
  "Preliminary observation — not a diagnosis": "शुरुआती अवलोकन, बीमारी की पहचान नहीं",
  // reference content in backend/data/crop_knowledge.json (stage text)
  "Fruits are sizing up rapidly. Keeping them well-fed and protected from insects is the priority.":
    "फल तेज़ी से बड़े हो रहे हैं। उन्हें अच्छा पोषण देना और कीड़ों से बचाना सबसे ज़रूरी है।",
  "Growth is slowing down and flower buds are beginning to form. The tree is preparing to flower.":
    "बढ़त धीमी हो रही है और फूल की कलियाँ बनने लगी हैं। पेड़ फूलने की तैयारी में है।",
  "Harvest is done and your trees are resting and rebuilding. New shoots are emerging from the pruned branches.":
    "कटाई हो चुकी है और पेड़ आराम करके फिर से तैयार हो रहे हैं। छँटाई की डालियों से नई कोंपलें निकल रही हैं।",
  "The monsoon is ending and your trees are continuing to grow strongly. Canopy training and drainage are the main focus now.":
    "मानसून खत्म हो रहा है और पेड़ अच्छी तरह बढ़ रहे हैं। अब छतरी को आकार देने और पानी निकासी पर ध्यान दें।",
  "This is the deliberate dry period. Stopping water now causes all fruits to ripen together at the same time.":
    "यह जान-बूझकर रखा गया सूखा दौर है। अभी पानी रोकने से सारे फल एक साथ पकते हैं।",
  "Your fruits are ready to pick. Harvest firm-mature fruits carefully for best market quality.":
    "आपके फल तोड़ने लायक हैं। बाज़ार में अच्छे भाव के लिए सख्त और पके फल सावधानी से तोड़ें।",
  "Your trees are flowering and small fruits are forming. This is the most important time for water and nutrition.":
    "पेड़ों में फूल आ रहे हैं और छोटे फल बन रहे हैं। पानी और पोषण के लिए यह सबसे ज़रूरी समय है।",
  "Your trees are putting on branches and leaves. This is the main growing phase where the tree builds its shape.":
    "पेड़ों में डालियाँ और पत्ते आ रहे हैं। यह मुख्य बढ़त का दौर है जिसमें पेड़ का आकार बनता है।",
  "Your trees have just been planted and are settling into the soil. Roots are growing and the tree is finding its footing.":
    "पेड़ अभी लगाए गए हैं और मिट्टी में जम रहे हैं। जड़ें बढ़ रही हैं और पेड़ अपनी जगह बना रहा है।",
  "Stop all irrigation completely this week. Do not water at all — this is intentional and important.":
    "इस हफ़्ते सिंचाई पूरी तरह बंद रखें। बिल्कुल पानी न दें। यह जान-बूझकर है और ज़रूरी है।",
  "Give 10 grams of 19-19-19 water-soluble fertiliser per plant each week. Add 2 grams of humic acid per plant each week.":
    "हर पौधे को हर हफ़्ते 10 ग्राम 19-19-19 पानी में घुलने वाली खाद दें। साथ में हर पौधे को हर हफ़्ते 2 ग्राम ह्यूमिक एसिड दें।",
  "Give 10 grams of SOP fertiliser per plant each week. Add 3 grams of calcium nitrate per plant each week.":
    "हर पौधे को हर हफ़्ते 10 ग्राम SOP खाद दें। साथ में हर पौधे को हर हफ़्ते 3 ग्राम कैल्शियम नाइट्रेट दें।",
  "Give 5 grams of 19-19-19 water-soluble fertiliser per plant each week through the drip system.":
    "ड्रिप से हर पौधे को हर हफ़्ते 5 ग्राम 19-19-19 पानी में घुलने वाली खाद दें।",
  "Give 5 grams of MKP fertiliser per plant each week in Tank B. Add 5 grams of calcium nitrate per plant each week in Tank A.":
    "हर पौधे को हर हफ़्ते 5 ग्राम MKP खाद टैंक B में दें। हर पौधे को हर हफ़्ते 5 ग्राम कैल्शियम नाइट्रेट टैंक A में दें।",
  "Give 5 grams of SOP fertiliser per plant each week for 2 weeks after harvest.":
    "कटाई के बाद 2 हफ़्ते तक हर पौधे को हर हफ़्ते 5 ग्राम SOP खाद दें।",
  "Give 7 grams of 19-19-19 water-soluble fertiliser per plant each week through the drip system.":
    "ड्रिप से हर पौधे को हर हफ़्ते 7 ग्राम 19-19-19 पानी में घुलने वाली खाद दें।",
  "Give 8 grams of 12-6-20 water-soluble fertiliser per plant each week. Add 1 gram of iron chelate per plant each week.":
    "हर पौधे को हर हफ़्ते 8 ग्राम 12-6-20 पानी में घुलने वाली खाद दें। साथ में हर पौधे को हर हफ़्ते 1 ग्राम आयरन केलेट दें।",
  "Give 8 grams of 8-8-32 water-soluble fertiliser per plant each week. Add 3 grams of calcium nitrate per plant each week.":
    "हर पौधे को हर हफ़्ते 8 ग्राम 8-8-32 पानी में घुलने वाली खाद दें। साथ में हर पौधे को हर हफ़्ते 3 ग्राम कैल्शियम नाइट्रेट दें।",
  "No fertiliser this week. The stress period must not be interrupted.":
    "इस हफ़्ते कोई खाद नहीं। सूखे के दौर को बीच में न तोड़ें।",
  "None — drought stress period": "कोई नहीं, सूखे का दौर",
  "SOP (post-harvest)": "SOP (कटाई के बाद)",
  "Anthracnose / leaf blight": "एंथ्रेक्नोज़ / पत्ती झुलसा", "Bark caterpillar": "छाल की इल्ली",
  "Fruit fly / bag damage": "फल मक्खी / थैली को नुकसान", "Mealybug / cottony scale": "मीलीबग / रूई जैसा शल्क कीट",
  "Post-harvest disease": "कटाई के बाद की बीमारी", "Premature fruit drop": "फल का समय से पहले गिरना",
  "Stem borer": "तना छेदक", "Stem borer (new shoots)": "तना छेदक (नई कोंपलें)",
  "Inspect bags for holes or insect entry": "थैलियों में छेद या कीड़े के घुसने के निशान देखें",
  "Inspect fruit fly traps daily": "फल मक्खी के जाल रोज़ देखें",
  "Inspect harvested fruit for rot or fungal patches": "तोड़े गए फलों में सड़न या फफूँद के धब्बे देखें",
  "Inspect new shoot tips for wilting": "नई कोंपलों के सिरों पर मुरझाना देखें",
  "Inspect shoot tips for wilting or dead tips": "टहनी के सिरों पर मुरझाना या सूखे सिरे देखें",
  "Inspect stem base for white sticky patches": "तने के निचले हिस्से पर सफ़ेद चिपचिपे धब्बे देखें",
  "Inspect stems for frass (sawdust-like excreta) or holes": "तनों पर बुरादे जैसा मल या छेद देखें",
  "Look for dark spots or blotches on leaf tips": "पत्तियों के सिरों पर काले धब्बे देखें",
  "Walk the orchard and check for fallen fruit": "बाग में घूमकर गिरे हुए फल देखें",
  "Apply copper oxychloride spray if symptoms are found on more than 10% of leaves":
    "अगर 10% से ज़्यादा पत्तियों पर लक्षण दिखें तो कॉपर ऑक्सीक्लोराइड का स्प्रे करें",
  "Remove affected shoot, insert wire into entry hole to kill larva": "प्रभावित टहनी हटाएँ और छेद में तार डालकर इल्ली को मारें",
  "Remove affected shoot; check root zone for collar rot symptoms": "प्रभावित टहनी हटाएँ और जड़ के पास कॉलर सड़न के लक्षण देखें",
  "Remove and burn diseased fruit; do not compost": "रोगी फल हटाकर जला दें, खाद में न डालें",
  "Remove and dispose of fallen fruit away from the orchard": "गिरे हुए फल उठाकर बाग से दूर नष्ट करें",
  "Remove by hand or apply neem oil spray if present": "हाथ से हटाएँ, या कीट हों तो नीम तेल का स्प्रे करें",
  "Remove caterpillar manually; apply chlorpyrifos paste on wound": "इल्ली को हाथ से निकालें और घाव पर क्लोरपाइरीफॉस का लेप लगाएँ",
  "Replace bait in traps; do NOT spray insecticide during flowering": "जाल में चारा बदलें। फूल आने के समय कीटनाशक का स्प्रे न करें",
  "Replace damaged bags; install additional fruit fly traps": "फटी थैलियाँ बदलें और फल मक्खी के और जाल लगाएँ",
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
  // plan tasks (backend/routers/plan.py) and stage text (crop_knowledge.json)
  [/^activity_type must be one of: (.+)$/, (m) =>
    `गतिविधि का प्रकार इनमें से एक होना चाहिए: ${m[1].split(", ").map((x) => activityTypeLabel(x, "hi")).join(", ")}।`],
  [/^area_unit must be one of: (.+)$/, (m) =>
    `क्षेत्रफल की इकाई इनमें से एक होनी चाहिए: ${m[1].split(", ").map((x) => UNIT_HI[x.toLowerCase()] || x).join(", ")}।`],
  [/^Water every day\. Give (\d+) litres per plant each day\.$/,
    (m) => `रोज़ पानी दें। हर पौधे को रोज़ ${m[1]} लीटर दें।`],
  [/^Restart watering\. Give (\d+) litres per plant each day\.$/,
    (m) => `सिंचाई फिर शुरू करें। हर पौधे को रोज़ ${m[1]} लीटर दें।`],
  [/^Fertilizer — (.+)$/, (m, lang) => `खाद — ${translateApiText(m[1], lang)}`],
  [/^Check: (.+)$/, (m, lang) => `जाँच: ${translateApiText(m[1], lang)}`],
  [/^(.+)\. (.+)$/, (m, lang) => {
    // "<check>. <action>" description of a pest task
    const a = EXACT[m[1]], b = EXACT[m[2]];
    return a && b ? `${a}। ${b}` : null;
  }],
  [/^You are in the (.+) stage \((\d+) months since planting\)\. Reference tasks are shown below\.$/,
    (m, lang) => `आप ${translateApiText(m[1], lang)} चरण में हैं (रोपण के ${m[2]} महीने बीते)। नीचे संदर्भ कार्य दिखाए गए हैं।`],
  [/^Harvest can only be logged at the harvest stage\. Current stage: (.+)\.$/,
    (m, lang) => `कटाई सिर्फ़ कटाई वाले चरण में दर्ज हो सकती है। अभी का चरण: ${translateApiText(m[1], lang)}।`],
];

const UNIT_HI = {
  kg: "किग्रा", g: "ग्राम", litres: "लीटर", liters: "लीटर", l: "लीटर", ml: "मिली", bags: "बोरे", units: "इकाई",
  hours: "घंटे", acres: "एकड़", hectares: "हेक्टेयर", sqm: "वर्ग मीटर", quintal: "क्विंटल",
};

const CATEGORY_HI = {
  input: "खाद, दवा और अन्य सामान", labour: "मज़दूरी", irrigation_electricity: "सिंचाई और बिजली", machinery: "मशीनरी",
  packaging: "पैकिंग", transport: "ढुलाई", rent_lease: "किराया / पट्टा", services: "सेवाएँ", other: "अन्य",
};

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
  const key = String(type ?? "").toLowerCase();
  return ACTIVITY_HI[key] || CATEGORY_HI[key] || String(type ?? "");
}

/** Hindi unit ("kg" -> "किग्रा"); unknown units, and composite ones such as "litres/day", go through the text table. */
export function unitLabel(unit, lang) {
  const s = String(unit ?? "");
  if (lang !== "hi" || !s) return s;
  return UNIT_HI[s.toLowerCase()] || translateApiText(s, lang);
}
